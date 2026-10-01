"""Prova offline do qualidade.py (M4.4, 6.2): sem ligação e sem LiveKit.

Gera sinais com valores conhecidos (fala sintética + ruído branco em SNR
definida, fala baixa, clipping, buracos de silêncio digital, só ruído, silêncio
total, banda de telefone), alimenta o MedidorQualidade em quadros de 10 ms (como
o rtc.AudioStream entrega) e compara o esperado com o medido. Mede também o
custo de CPU por segundo de áudio.

Rodar:  .venv\\Scripts\\python.exe scripts\\testa_qualidade.py [--wav-dir PASTA]
"""

from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from qualidade import MedidorQualidade, ResumoQualidade  # noqa: E402

SR = 16000
DUR = 30.0
rng = np.random.default_rng(42)


def fala_sintetica(dur: float, nivel_dbfs: float) -> tuple[np.ndarray, np.ndarray]:
    """Voz artificial: harmônicos de f0 variando 110-190 Hz, sílabas a ~4 Hz,
    rajadas de 1,5 s de fala e 0,7 s de pausa. Devolve (sinal float, máscara de fala)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0 = 150 + 40 * np.sin(2 * np.pi * 0.7 * t)
    fase = 2 * np.pi * np.cumsum(f0) / SR
    voz = sum(np.sin(k * fase) / k for k in range(1, 16))
    silabas = 0.35 + 0.65 * np.sin(np.pi * 4 * t) ** 2
    ciclo = (t % 2.2) < 1.5
    s = voz * silabas * ciclo
    alvo = 10 ** (nivel_dbfs / 10)
    s *= np.sqrt(alvo / np.mean(s[ciclo] ** 2))
    return s, ciclo


def ruido(n: int, potencia: float) -> np.ndarray:
    return rng.normal(0, np.sqrt(potencia), n)


def banda_telefone(x: np.ndarray) -> np.ndarray:
    """300-3400 Hz (o que sobra de um G.711 de 8 kHz reamostrado para 16 kHz)."""
    f = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1 / SR)
    f[(freqs < 300) | (freqs > 3400)] = 0
    return np.fft.irfft(f, x.size)


def para_int16(x: np.ndarray) -> np.ndarray:
    return np.clip(np.round(x * 32768), -32768, 32767).astype(np.int16)


def insere_buracos(pcm: np.ndarray, por_janela: list[int]) -> np.ndarray:
    """Zera trechos (ms) em posições espalhadas de cada janela de 10 s."""
    pcm = pcm.copy()
    janela = 10 * SR
    for inicio in range(0, pcm.size, janela):
        for i, ms in enumerate(por_janela):
            p = inicio + int((i + 0.5) * janela / len(por_janela))
            pcm[p: p + int(ms * SR / 1000)] = 0
    return pcm


def mede(pcm: np.ndarray, limites=(10.0, 2, 5.0)) -> tuple[list[dict], dict, float]:
    med = MedidorQualidade(SR)
    res = ResumoQualidade(*limites)
    janelas = []
    t0 = time.process_time()
    for i in range(0, pcm.size, SR // 100):  # quadros de 10 ms
        for m in med.alimenta(pcm[i: i + SR // 100]):
            m.update(res.adiciona(m))
            janelas.append(m)
    ultima = med.fecha()
    if ultima:
        ultima.update(res.adiciona(ultima))
        janelas.append(ultima)
    cpu = time.process_time() - t0
    return janelas, res.resumo(), cpu


def caso_fala_ruido(snr: float, nivel: float = -20.0, telefone: bool = False) -> np.ndarray:
    s, _ = fala_sintetica(DUR, nivel)
    x = s + ruido(s.size, 10 ** (nivel / 10) / 10 ** (snr / 10))
    return para_int16(banda_telefone(x) if telefone else x)


CASOS = []


def caso(nome, esperado, checa, limites=(10.0, 2, 5.0)):
    def deco(f):
        CASOS.append((nome, esperado, checa, limites, f))
        return f
    return deco


def perto(v, alvo, tol):
    return v is not None and abs(v - alvo) <= tol


@caso("limpo (ruído -80 dBFS)", "SNR > 40, fala ~-20, sem buraco/clip",
      lambda j, r: r["snr_mediana_db"] > 40 and perto(r["fala_mediana_dbfs"], -20, 1.5) and r["buracos_qtd"] == 0 and r["clipping_pct_max"] == 0)
def _():
    return caso_fala_ruido(60)


for _snr in (20, 10, 5):
    @caso(f"SNR {_snr} dB", f"SNR {_snr} ±2, ruído ~{-20 - _snr}",
          lambda j, r, s=_snr: perto(r["snr_mediana_db"], s, 2.0) and perto(r["ruido_mediana_dbfs"], -20 - s, 1.0))
    def _(s=_snr):
        return caso_fala_ruido(s)


@caso("SNR 0 dB", "todas as janelas ruins (SNR baixa ou ruído alto sem fala) e gatilho na 2",
      lambda j, r: r["janelas_ruins"] == len(j) and r["gatilho_dispararia_na_janela"] == 2)
def _():
    return caso_fala_ruido(0)


@caso("fala baixa -38 dBFS, SNR 15", "fala ~-38, SNR 15 ±2",
      lambda j, r: perto(r["fala_mediana_dbfs"], -38, 1.5) and perto(r["snr_mediana_db"], 15, 2.0))
def _():
    return caso_fala_ruido(15, nivel=-38)


_tel = {}


@caso("telefone 300-3400 Hz (SNR 10 antes do filtro)", "SNR real depois do filtro ±2",
      lambda j, r: perto(r["snr_mediana_db"], _tel["snr"], 2.0))
def _():
    # o filtro corta a fundamental da voz e parte do ruído: a SNR real muda;
    # calcula a esperada com fala e ruído filtrados separadamente
    s, ativo = fala_sintetica(DUR, -20)
    n = ruido(s.size, 10 ** (-30 / 10))
    sf, nf = banda_telefone(s), banda_telefone(n)
    _tel["snr"] = round(10 * np.log10(np.mean(sf[ativo] ** 2) / np.mean(nf ** 2)), 1)
    return para_int16(sf + nf)


_clip_esperado = {}


@caso("clipping (ganho +12 dB, estoura)", "clipping = % calculado no sinal",
      lambda j, r: perto(r["clipping_pct_max"], _clip_esperado["max"], 0.05))
def _():
    s, _ = fala_sintetica(DUR, -8)
    x = (s + ruido(s.size, 10 ** (-40 / 10))) * 4
    pcm = para_int16(x)
    por_janela = [np.mean(np.abs(pcm[i:i + 10 * SR].astype(np.int32)) >= 32440) * 100 for i in range(0, pcm.size, 10 * SR)]
    _clip_esperado["max"] = round(max(por_janela), 2)
    return pcm


@caso("buracos 5x120 ms + 3x60 ms por janela", "5 buracos/janela (60 ms não contam), 6,0%",
      lambda j, r: all(x["buracos_qtd"] == 5 for x in j) and perto(r["buracos_pct"], 6.0, 0.25))
def _():
    return insere_buracos(caso_fala_ruido(20), [120, 60, 120, 60, 120, 60, 120, 120])


@caso("lacunas da seção 7.3 (1x120 ms a cada 10 s)", "1 buraco/janela, 1,2%",
      lambda j, r: all(x["buracos_qtd"] == 1 for x in j) and perto(r["buracos_pct"], 1.2, 0.25))
def _():
    return insere_buracos(caso_fala_ruido(20), [120])


@caso("só ruído -50 dBFS", "fala ~0%, sem SNR",
      lambda j, r: (r["fala_pct_mediana"] or 0) <= 2 and r["snr_mediana_db"] is None)
def _():
    return para_int16(ruido(int(DUR * SR), 10 ** (-50 / 10)))


@caso("silêncio digital total", "silêncio digital 100%, 0 buracos, janelas não ruins",
      lambda j, r: perto(r["silencio_digital_pct"], 100, 0.1) and r["buracos_qtd"] == 0 and r["janelas_ruins"] == 0)
def _():
    return np.zeros(int(DUR * SR), dtype=np.int16)


@caso("pausas de 3 s em silêncio digital (DTX) + fala SNR 20", "0 buracos, silêncio digital ~30%, SNR ~20",
      lambda j, r: r["buracos_qtd"] == 0 and perto(r["silencio_digital_pct"], 30, 1.0) and perto(r["snr_mediana_db"], 20, 2.0))
def _():
    pcm = caso_fala_ruido(20)
    for inicio in range(0, pcm.size, 10 * SR):
        pcm[inicio + 5 * SR: inicio + 8 * SR] = 0
    return pcm


@caso("gatilho: SNR 5 com limite 10 dB / 2 janelas", "dispararia na janela 2",
      lambda j, r: r["gatilho_dispararia_na_janela"] == 2)
def _():
    return caso_fala_ruido(5)


@caso("vozes contínuas ao fundo (TV): fala quase 100%", "motivo fala_continua em todas as janelas, gatilho na 2",
      lambda j, r: all("fala_continua" in x["motivos"] for x in j) and r["gatilho_dispararia_na_janela"] == 2)
def _():
    s, _ = fala_sintetica(DUR, -20)
    s2, _ = fala_sintetica(DUR + 1.1, -26)
    x = s + s2[int(1.1 * SR):]  # segunda "voz" preenche as pausas da primeira
    return para_int16(x + ruido(x.size, 10 ** (-70 / 10)))


@caso("gatilho: SNR 20 com limite 10 dB / 2 janelas", "não dispararia",
      lambda j, r: r["gatilho_dispararia_na_janela"] is None)
def _():
    return caso_fala_ruido(20)


TEXTOS_PACIENTE = [
    ("Meu nome é Maria da Silva Souza.", []),
    ("Sim, está correto.", []),
    ("Como assim? Que dia é a consulta?", []),
    ("Quero marcar um exame para mim e para a minha irmã.", []),
    ("mi hermana y mi da Silva Souza", ["espanhol"]),
    ("¿Qué?", ["espanhol"]),
    ("Hola, necesito una cita", ["espanhol"]),
    ("Hola, buenos días.", ["espanhol"]),
    ("Usted me puede ayudar.", ["espanhol"]),
    ("Eso no es.", ["espanhol"]),
    ("Eso es.", ["espanhol"]),
    ("Não é isso, é o número um.", []),
    ("Não entendo nada. Puede hablar más despacio?", ["espanhol"]),
    ("Bom dia, tudo bem? Hoje eu queria saber como marcar.", []),
    ("", ["transcricao_vazia"]),
    ("??", ["transcricao_vazia"]),
    ("...", ["transcricao_vazia"]),
]
TEXTOS_IA = [
    ("Olá, seja bem-vinda à Clínica Coopab. Qual o seu nome completo?", []),
    ("Obrigada, Maria. Agora me informe o seu CPF, por favor.", []),
    ("Desculpe, não entendi. Pode repetir, por favor?", ["ia_pediu_repeticao"]),
    ("Não consegui ouvir direito, a ligação está cortando.", ["ia_pediu_repeticao"]),
    ("Poderia falar um pouco mais alto?", ["ia_pediu_repeticao"]),
    ("¿Podría repetir su nombre?", ["ia_em_espanhol"]),
    ("Por favor, poderia falar em português? Qual é o seu nome completo?", ["ia_pediu_repeticao"]),
]


def testa_textos() -> int:
    from qualidade import ContadorCompreensao, motivos_ia, motivos_paciente
    falhas = 0
    for texto, esperado in TEXTOS_PACIENTE:
        obtido = motivos_paciente(texto)
        falhas += obtido != esperado
        print(f"[{'PASS' if obtido == esperado else 'FAIL'}] paciente {texto!r} -> {obtido}")
    for texto, esperado in TEXTOS_IA:
        obtido = motivos_ia(texto)
        falhas += obtido != esperado
        print(f"[{'PASS' if obtido == esperado else 'FAIL'}] IA {texto[:50]!r} -> {obtido}")

    # sequência (t em segundos): incompreensão (paciente + IA = 1 incidente), outra com a IA ANTES da
    # transcrição do paciente (ordem real do Gemini; dispararia com máx. 2), conversa normal zera, nova = 1
    c = ContadorCompreensao(2)
    a1 = c.fala_paciente("mi hermana y mi da Silva Souza", 10)
    a2 = c.fala_ia("Desculpe, não entendi. Pode repetir?", 11)
    b1 = c.fala_ia("Não consegui ouvir, pode repetir?", 30)
    b2 = c.fala_paciente("??", 31)
    c.fala_paciente("Maria da Silva Souza.", 50)
    n1 = c.fala_ia("Obrigada, Maria. Qual o seu CPF?", 52)
    c.fala_paciente("Cinco dois nove.", 70)
    d1 = c.fala_ia("Não entendi, pode repetir o CPF?", 72)
    ok = (a1["incidente"] == 1 and not a1["mesclado"] and a1["seguidas"] == 1
          and a2["incidente"] == 1 and a2["mesclado"] and a2["motivos"] == ["espanhol", "ia_pediu_repeticao"]
          and b1["incidente"] == 2 and b1["seguidas"] == 2 and b1["gatilho_dispararia"] and b2["mesclado"]
          and n1 is None and d1["incidente"] == 3 and d1["seguidas"] == 1
          and c.resumo() == {"incompreensoes": 3, "incompreensoes_max_seguidas": 2, "incompreensao_gatilho_no_incidente": 2, "max_incompreensoes": 2})
    falhas += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] contador: incidentes mesclados em qualquer ordem, gatilho no 2º, resposta normal zera -> {c.resumo()}")
    return falhas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav-dir", help="grava os WAVs gerados nesta pasta (para ouvir)")
    args = ap.parse_args()

    falhas = 0
    cpu_total = 0.0
    audio_total = 0.0
    for nome, esperado, checa, limites, gera in CASOS:
        pcm = gera()
        janelas, r, cpu = mede(pcm, limites)
        cpu_total += cpu
        audio_total += pcm.size / SR
        ok = bool(checa(janelas, r))
        falhas += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {nome} | esperado: {esperado}"
              + (f" (= {_tel['snr']} dB)" if nome.startswith("telefone") else ""))
        print(f"       medido: SNR med {r['snr_mediana_db']} (mín {r['snr_min_db']}) | fala {r['fala_mediana_dbfs']} dBFS"
              f" ({r['fala_pct_mediana']}%) | ruído {r['ruido_mediana_dbfs']} | clip máx {r['clipping_pct_max']}%"
              f" | buracos {r['buracos_qtd']} ({r['buracos_pct']}%) | gatilho {r['gatilho_dispararia_na_janela']}")
        if args.wav_dir:
            Path(args.wav_dir).mkdir(parents=True, exist_ok=True)
            with wave.open(str(Path(args.wav_dir) / (nome.split(" (")[0].replace(" ", "_").replace(":", "") + ".wav")), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes(pcm.tobytes())

    print(f"\nCPU: {1000 * cpu_total / audio_total:.2f} ms de CPU por segundo de áudio "
          f"({100 * cpu_total / audio_total:.2f}% de um núcleo por chamada)")
    print(f"RESULTADO (sinal): {len(CASOS) - falhas}/{len(CASOS)} casos passaram\n")
    falhas_txt = testa_textos()
    total_txt = len(TEXTOS_PACIENTE) + len(TEXTOS_IA) + 1
    print(f"RESULTADO (compreensão): {total_txt - falhas_txt}/{total_txt} casos passaram")
    return 1 if falhas or falhas_txt else 0


if __name__ == "__main__":
    sys.exit(main())
