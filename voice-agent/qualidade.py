"""Métricas de sinal do áudio do paciente (M4.4 fase 1, modo sombra).

Só mede: recebe PCM int16 mono (16 kHz no worker) e devolve, a cada janela
(10 s), nível de fala e de ruído de fundo (dBFS), SNR estimada, % de clipping
e buracos (silêncio digital >= 100 ms). Não sabe nada de LiveKit nem do RAPIA:
o agent.py alimenta os quadros e publica os eventos; scripts/testa_qualidade.py
prova os números com sinais gerados.

Fala x ruído, por janela: piso de ruído = percentil 10 da energia dos quadros
de 20 ms (sem os de silêncio digital); quadro é fala acima de piso + 6 dB, com
histerese (sai abaixo de piso + 3 dB) e 200 ms de sustentação. SNR = potência
dos quadros de fala menos a do ruído (subtração de potência), sobre a do ruído.
É heurística: TV ou rua com vozes também contam como "fala", e com SNR muito
baixa a fala nem se destaca do piso — por isso "sem fala + ruído alto" também
marca a janela como ruim. Os números finais vêm da calibração com ligações
reais (M4.4, 6.6 no TODO).
"""

from __future__ import annotations

import math
import re
import time
import unicodedata
from typing import Any

import numpy as np

FUNDO_ESCALA = 32768.0
LIMIAR_ZERO = 2           # |amostra| <= 2 conta como silêncio digital (reamostragem pode deixar ±1)
LIMIAR_CLIP = 32440       # ~0,99 do fundo de escala
BURACO_MIN_MS = 100
# Silêncio digital mais longo que isso não é queda de áudio: é o lado do
# paciente calado com supressão de silêncio (DTX do Opus/navegador, ou
# microfone sem envio) — vai para silencio_digital_pct, que não marca a janela
# como ruim. Quedas de rede/jitter reais são curtas (as da seção 7.3: ~0,12 s).
BURACO_MAX_MS = 1000
PISO_PERCENTIL = 10
LIGA_FALA_DB = 6.0        # quadro vira fala acima de piso + 6 dB...
DESLIGA_FALA_DB = 3.0     # ...e só volta a ruído abaixo de piso + 3 dB
SEGURA_FALA_MS = 200      # e depois de 200 ms abaixo (sustentação)
FALA_MIN_DBFS = -55.0     # abaixo disso nunca é fala (linha quase muda)
FALA_MIN_PCT = 3.0        # menos que isso de fala na janela: não calcula SNR
# Provisório até a calibração: janela sem fala detectável, mas com ruído de
# fundo alto (a fala some no ruído, SNR ~0), também conta como ruim.
RUIDO_ALTO_DBFS = -30.0
# Provisório (calibração de 26/09/2026, ligação 105 com TV alta): o celular
# suprime o ruído estacionário, mas vozes de TV/pessoas ao fundo passam como
# "fala" e a SNR continua alta. O sinal que separou foi a fala quase contínua:
# TV 94-99,6% da janela; viva-voz até 88%; ambiente silencioso até 50%.
FALA_CONTINUA_PCT = 90.0


def dbfs(potencia: float | None) -> float | None:
    """Potência média (amostras normalizadas em [-1, 1]) -> dBFS; None se zero."""
    return None if not potencia or potencia <= 0 else 10.0 * math.log10(potencia)


def _r(valor: float | None, casas: int = 1) -> float | None:
    return None if valor is None else round(valor, casas)


def _corridas(mascara: np.ndarray) -> np.ndarray:
    """Comprimentos das sequências de True num vetor booleano."""
    if not mascara.any():
        return np.zeros(0, dtype=np.int64)
    d = np.diff(np.concatenate(([0], mascara.view(np.int8), [0])))
    return np.flatnonzero(d == -1) - np.flatnonzero(d == 1)


class MedidorQualidade:
    """Acumula quadros e fecha uma janela a cada `janela_s` segundos.

    Uso: `for m in medidor.alimenta(pcm_int16): publica(m)`; no fim,
    `medidor.fecha()` devolve a janela parcial (se tiver >= 2 s). Custo: todo o
    cálculo pesado é vetorizado no fechamento da janela (~1,5 ms de CPU por
    segundo de áudio medido em scripts/testa_qualidade.py).
    """

    def __init__(self, sample_rate: int = 16000, janela_s: float = 10.0, quadro_ms: int = 20) -> None:
        self.sample_rate = sample_rate
        self.quadro_ms = quadro_ms
        self.quadro = int(sample_rate * quadro_ms / 1000)
        self.amostras_por_janela = self.quadro * int(round(janela_s * 1000 / quadro_ms))
        self._segura_max = max(1, SEGURA_FALA_MS // quadro_ms)
        self._buraco_min = int(sample_rate * BURACO_MIN_MS / 1000)
        self._buraco_max = int(sample_rate * BURACO_MAX_MS / 1000)
        self._partes: list[np.ndarray] = []
        self._n = 0
        self._janela_seq = 0

    def alimenta(self, pcm: np.ndarray) -> list[dict[str, Any]]:
        pcm = np.asarray(pcm, dtype=np.int16).reshape(-1)
        prontas = []
        while pcm.size:
            falta = self.amostras_por_janela - self._n
            parte, pcm = pcm[:falta], pcm[falta:]
            self._partes.append(parte.copy())
            self._n += parte.size
            if self._n >= self.amostras_por_janela:
                prontas.append(self._fecha_janela())
        return prontas

    def fecha(self, minimo_s: float = 2.0) -> dict[str, Any] | None:
        """Janela parcial do fim da chamada (descartada se curta demais)."""
        if self._n < minimo_s * self.sample_rate:
            self._partes, self._n = [], 0
            return None
        return self._fecha_janela()

    def _classifica(self, niveis: np.ndarray, zeros: np.ndarray) -> np.ndarray:
        fala = np.zeros(niveis.size, dtype=bool)
        validos = niveis[~zeros]
        if validos.size == 0:
            return fala
        piso = float(np.percentile(validos, PISO_PERCENTIL))
        ativo, segura = False, 0
        for i, nivel in enumerate(niveis):
            if zeros[i]:
                continue
            acima = nivel - piso
            if nivel >= FALA_MIN_DBFS and (acima >= LIGA_FALA_DB or (ativo and acima >= DESLIGA_FALA_DB)):
                ativo, segura = True, self._segura_max
            elif ativo and segura > 0:
                segura -= 1
            else:
                ativo = False
            fala[i] = ativo
        return fala

    def _fecha_janela(self) -> dict[str, Any]:
        self._janela_seq += 1
        pcm = np.concatenate(self._partes) if self._partes else np.zeros(0, dtype=np.int16)
        self._partes, self._n = [], 0

        amostras = pcm.astype(np.int32)
        absx = np.abs(amostras)
        nq = amostras.size // self.quadro
        quadros = amostras[: nq * self.quadro].reshape(nq, self.quadro) / FUNDO_ESCALA
        potencias = (quadros ** 2).mean(axis=1) if nq else np.zeros(0)
        zeros_q = absx[: nq * self.quadro].reshape(nq, self.quadro).max(axis=1) <= LIMIAR_ZERO if nq else np.zeros(0, bool)
        niveis = 10.0 * np.log10(np.maximum(potencias, 1e-12))

        fala = self._classifica(niveis, zeros_q)
        ruido = ~fala & ~zeros_q
        pot_fala = float(potencias[fala].mean()) if fala.any() else None
        pot_ruido = float(potencias[ruido].mean()) if ruido.any() else None
        fala_pct = 100.0 * fala.sum() / max(nq, 1)

        snr = None
        if pot_fala is not None and pot_ruido and fala_pct >= FALA_MIN_PCT:
            limpa = pot_fala - pot_ruido
            # fala que mal se distingue do ruído: SNR "0 dB ou menos" (não -inf)
            snr = 10.0 * math.log10(limpa / pot_ruido) if limpa > 0 else 0.0

        corridas = _corridas(absx <= LIMIAR_ZERO)
        buracos = corridas[(corridas >= self._buraco_min) & (corridas <= self._buraco_max)]
        silencio = corridas[corridas > self._buraco_max]
        pico = int(absx.max()) if absx.size else 0

        return {
            "janela": self._janela_seq,
            "duracao_s": _r(amostras.size / self.sample_rate),
            "fala_pct": _r(fala_pct),
            "fala_dbfs": _r(dbfs(pot_fala)),
            "ruido_dbfs": _r(dbfs(pot_ruido)),
            "snr_db": _r(snr),
            "clipping_pct": _r(100.0 * (absx >= LIMIAR_CLIP).sum() / max(absx.size, 1), 2),
            "buracos_qtd": int(buracos.size),
            "buracos_ms": int(round(1000 * buracos.sum() / self.sample_rate)),
            "buracos_pct": _r(100.0 * buracos.sum() / max(absx.size, 1)),
            # durações (ms) de cada buraco, para a calibração separar queda de rede de pausa em silêncio
            "buracos_lista_ms": [int(round(1000 * b / self.sample_rate)) for b in buracos[:20]],
            "silencio_digital_pct": _r(100.0 * silencio.sum() / max(absx.size, 1)),
            "pico_dbfs": _r(20.0 * math.log10(pico / FUNDO_ESCALA) if pico else None),
        }


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


# Espanhol: o Gemini, com áudio ruim de telefone, chegou a "ouvir" espanhol
# ("¿Qué?" da ligação 55; "mi hermana y mi da Silva Souza" no Playground com
# ruído). Palavras fortes bastam sozinhas; fracas só contam em dupla.
_ES_FORTES = {"usted", "hola", "gracias", "senor", "senora", "hermana", "hermano", "llamo", "nombre", "necesito",
              "quiero", "tengo", "puedo", "ayuda", "bueno", "buenos", "buenas", "muy", "entiendo", "despacio", "puede", "hablar", "eso"}
_ES_FRACAS = {"que", "como", "donde", "cual", "yo", "mi", "pero", "ahora", "si", "el", "y", "es", "no", "un"}
_PEDIDO_REPETICAO = re.compile(
    r"pode(ria)? (me )?repetir|repita|repete|nao (entendi|compreendi|ouvi|escutei)|nao consegui (ouvir|entender|escutar|compreender)"
    r"|nao ficou claro|(ligacao|audio|som) (esta |ta )?(ruim|cortando|falhando|baixo)|esta cortando|falar (um pouco )?mais alto"
    r"|pode(ria)? falar (novamente|de novo|outra vez)|nao (estou|to) (te )?(ouvindo|escutando)"
    r"|(fale|falar|responder|responda) em portugues"
)


def motivos_paciente(texto: str | None) -> list[str]:
    """Sinais de que a fala do paciente não foi entendida (pela transcrição)."""
    bruto = (texto or "").strip()
    if not bruto or re.fullmatch(r"[\W_?]*", bruto) or "??" in bruto:
        return ["transcricao_vazia"]
    if any(c in bruto for c in "¿¡ñÑ"):
        return ["espanhol"]
    palavras = re.findall(r"[a-z]+", _sem_acento(bruto))
    fortes = sum(1 for p in palavras if p in _ES_FORTES)
    fracas = sum(1 for p in palavras if p in _ES_FRACAS)
    if fortes >= 1 and fortes + fracas >= 2:
        return ["espanhol"]
    return []


def motivos_ia(texto: str | None) -> list[str]:
    """Sinais, na fala da IA, de que ela não entendeu o paciente."""
    bruto = (texto or "").strip()
    saida = []
    if _PEDIDO_REPETICAO.search(_sem_acento(bruto)):
        saida.append("ia_pediu_repeticao")
    if any(c in bruto for c in "¿¡"):
        saida.append("ia_em_espanhol")
    return saida


class ContadorCompreensao:
    """Conta incompreensões seguidas (modo sombra: só registra).

    Incidente = sinais que chegam a até MESCLA_S um do outro, em qualquer ordem:
    a transcrição do paciente em espanhol e a IA pedindo para repetir são o
    MESMO incidente. (O Gemini às vezes entrega a fala da IA ANTES da
    transcrição do paciente que ela respondeu — achado no Playground.) Cada
    sinal vira um evento; os do mesmo incidente repetem o número e
    `mesclado=True`. A sequência zera quando a IA responde normalmente a uma
    fala boa do paciente, fora da janela do último incidente."""

    MESCLA_S = 6.0

    def __init__(self, max_incompreensoes: int) -> None:
        self.max = max(1, max_incompreensoes)
        self.seguidas = 0
        self.total = 0
        self.max_seguidas = 0
        self.gatilho_no_incidente: int | None = None
        self._t_incidente: float | None = None
        self._motivos_incidente: list[str] = []
        self._paciente_ok = False

    def fala_paciente(self, texto: str | None, t: float | None = None) -> dict[str, Any] | None:
        motivos = motivos_paciente(texto)
        self._paciente_ok = not motivos
        return self._registra(motivos, t, paciente=texto) if motivos else None

    def fala_ia(self, texto: str | None, t: float | None = None) -> dict[str, Any] | None:
        """Devolve o payload do evento comprehension_miss, ou None se não houve."""
        t = time.monotonic() if t is None else t
        motivos = motivos_ia(texto)
        if motivos:
            return self._registra(motivos, t, ia=texto)
        fora = self._t_incidente is None or t - self._t_incidente > self.MESCLA_S
        if self._paciente_ok and fora:
            self.seguidas = 0
        return None

    def _registra(self, motivos: list[str], t: float | None, paciente: str | None = None, ia: str | None = None) -> dict[str, Any]:
        t = time.monotonic() if t is None else t
        mesclado = self._t_incidente is not None and t - self._t_incidente <= self.MESCLA_S
        if mesclado:
            self._motivos_incidente += [m for m in motivos if m not in self._motivos_incidente]
        else:
            self.seguidas += 1
            self.total += 1
            self._motivos_incidente = list(motivos)
        self._t_incidente = t
        self.max_seguidas = max(self.max_seguidas, self.seguidas)
        dispararia = self.seguidas >= self.max
        if dispararia and self.gatilho_no_incidente is None:
            self.gatilho_no_incidente = self.total
        return {
            "incidente": self.total,
            "mesclado": mesclado,
            "motivos": list(self._motivos_incidente),
            "texto_paciente": (paciente or "").strip()[:300] if paciente is not None else None,
            "texto_ia": (ia or "").strip()[:300] if ia is not None else None,
            "seguidas": self.seguidas,
            "max_incompreensoes": self.max,
            "gatilho_dispararia": dispararia,
        }

    def resumo(self) -> dict[str, Any]:
        return {"incompreensoes": self.total, "incompreensoes_max_seguidas": self.max_seguidas,
                "incompreensao_gatilho_no_incidente": self.gatilho_no_incidente,
                "max_incompreensoes": self.max}


class ResumoQualidade:
    """Junta as janelas de uma chamada e diz se o gatilho de sinal TERIA disparado
    com os limites da versão (modo sombra: só registra, nunca transfere)."""

    def __init__(self, snr_min_db: float, janelas_seguidas: int, max_buracos_pct: float) -> None:
        self.snr_min_db = snr_min_db
        self.janelas_seguidas = max(1, janelas_seguidas)
        self.max_buracos_pct = max_buracos_pct
        self.janelas: list[dict[str, Any]] = []
        self._ruins_seguidas = 0
        self.max_ruins_seguidas = 0
        self.gatilho_janela: int | None = None

    def motivos(self, m: dict[str, Any]) -> list[str]:
        """Por que a janela é ruim (lista vazia = boa)."""
        saida = []
        if m["snr_db"] is not None and m["snr_db"] < self.snr_min_db:
            saida.append("snr_baixa")
        if m["snr_db"] is None and m["ruido_dbfs"] is not None and m["ruido_dbfs"] >= RUIDO_ALTO_DBFS:
            saida.append("ruido_alto_sem_fala")
        if m["buracos_pct"] > self.max_buracos_pct:
            saida.append("buracos")
        if m["fala_pct"] is not None and m["fala_pct"] >= FALA_CONTINUA_PCT:
            saida.append("fala_continua")
        return saida

    def adiciona(self, m: dict[str, Any]) -> dict[str, Any]:
        """Registra a janela e devolve os campos de avaliação a publicar junto."""
        self.janelas.append(m)
        motivos = self.motivos(m)
        if motivos:
            self._ruins_seguidas += 1
        elif m["snr_db"] is not None:
            # só uma janela com fala medida e boa zera a sequência; paciente
            # calado em ambiente silencioso não conta nem a favor nem contra
            self._ruins_seguidas = 0
        self.max_ruins_seguidas = max(self.max_ruins_seguidas, self._ruins_seguidas)
        dispararia = self._ruins_seguidas >= self.janelas_seguidas
        if dispararia and self.gatilho_janela is None:
            self.gatilho_janela = m["janela"]
        return {"motivos": motivos, "ruins_seguidas": self._ruins_seguidas, "gatilho_dispararia": dispararia}

    def resumo(self) -> dict[str, Any]:
        js = self.janelas

        def valores(chave: str) -> list[float]:
            return [j[chave] for j in js if j[chave] is not None]

        def mediana(chave: str) -> float | None:
            v = valores(chave)
            return _r(float(np.median(v))) if v else None

        dur = sum(j["duracao_s"] for j in js)
        buracos_ms = sum(j["buracos_ms"] for j in js)
        return {
            "janelas": len(js),
            "duracao_s": _r(dur),
            "snr_mediana_db": mediana("snr_db"),
            "snr_min_db": _r(min(valores("snr_db"))) if valores("snr_db") else None,
            "ruido_mediana_dbfs": mediana("ruido_dbfs"),
            "fala_mediana_dbfs": mediana("fala_dbfs"),
            "fala_pct_mediana": mediana("fala_pct"),
            "clipping_pct_max": max((j["clipping_pct"] for j in js), default=0.0),
            "buracos_qtd": sum(j["buracos_qtd"] for j in js),
            "buracos_pct": _r(100.0 * buracos_ms / 1000 / dur) if dur else 0.0,
            "silencio_digital_pct": _r(sum(j["silencio_digital_pct"] * j["duracao_s"] for j in js) / dur) if dur else 0.0,
            "janelas_ruins": sum(1 for j in js if self.motivos(j)),
            "max_ruins_seguidas": self.max_ruins_seguidas,
            "gatilho_dispararia_na_janela": self.gatilho_janela,
            "limites": {"snr_min_db": self.snr_min_db, "janelas_seguidas": self.janelas_seguidas,
                        "max_buracos_pct": self.max_buracos_pct},
        }
