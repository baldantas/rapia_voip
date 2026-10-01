"""Agente de voz do RAPIA (M1: prompt e tools vêm do RAPIA, não mais fixos aqui).

Fluxo: atende a ligação vinda do tronco SIP, busca no RAPIA (GET /voice/agents/
{id}/runtime) o prompt, a voz/modelo/temperatura e o catálogo de tools do
agente configurado, monta a sessão com isso e publica transcrição/eventos de
volta no RAPIA (POST /voice/worker/transcript e /voice/worker/tools/{name}).
O worker não sabe mais nada de negócio (nome/CPF, fila, etc.) — só mecânica de
sessão e HTTP. `agent_id` vem dos metadados do dispatch (scripts/dispatch.py);
sem isso, cai no `VOICE_AGENT_ID` do .env (útil para `agent.py console`, que
não passa por uma dispatch rule).

Playground (M3): o despacho vem do token do navegador (POST /voice/playground/
session) e traz também `version_id` (a versão exata, em geral o rascunho, a
carregar), `playground` e `max_seconds` (o LiveKit não limita a duração de uma
sessão; quem corta é o worker). Ligação real nunca traz esses campos e continua
carregando a versão publicada, sem limite de duração.

coletas.jsonl continua existindo como log local de depuração (não é mais fonte
de verdade — o banco do RAPIA é).

Rodar:  .venv\\Scripts\\python.exe agent.py dev
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np
from dotenv import load_dotenv
from google.genai import types
from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, ToolError, function_tool
from livekit.plugins import google

from qualidade import ContadorCompreensao, MedidorQualidade, ResumoQualidade

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

# o próprio CLI do livekit-agents configura o logging; aqui só pegamos o logger
logger = logging.getLogger("rapia-voice")

REGISTROS = BASE / "coletas.jsonl"

RAPIA_API_URL = os.getenv("RAPIA_API_URL", "http://api.ipsys/api").rstrip("/")
RAPIA_API_TOKEN = os.getenv("RAPIA_API_TOKEN", "")
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=8)

# ai -> fala do modelo; user -> fala do paciente. Não existe papel "agent"
# (atendente humano) nesta sessão: essa fala só existe depois que o LiveKit
# transfere áudio para o softphone do atendente (M2), fora do que o worker vê.
PAPEL_TRANSCRICAO = {"assistant": "ai", "user": "patient"}


def parametros_do_job(ctx: JobContext) -> dict[str, Any]:
    """Lê os metadados do despacho (JSON em ctx.job.metadata): `agent_id` é
    obrigatório na prática; `version_id`, `playground` e `max_seconds` só vêm do
    Playground. Sem agent_id (ex.: `agent.py console`), usa VOICE_AGENT_ID do
    .env (padrão: 1, o agente "Triagem Central" do seed)."""
    dados: dict[str, Any] = {}
    bruto = getattr(ctx.job, "metadata", None) or ""
    if bruto:
        try:
            lido = json.loads(bruto)
            if isinstance(lido, dict):
                dados = lido
        except (json.JSONDecodeError, TypeError):
            logger.warning("metadata do job não é um JSON válido: %r", bruto)

    try:
        agent_id = int(dados["agent_id"])
    except (KeyError, TypeError, ValueError):
        agent_id = int(os.getenv("VOICE_AGENT_ID", "1"))
        logger.info("Sem agent_id nos metadados do job; usando o padrão do .env (%s)", agent_id)

    def inteiro_positivo(chave: str) -> int | None:
        try:
            valor = int(dados[chave])
        except (KeyError, TypeError, ValueError):
            return None
        return valor if valor > 0 else None

    return {
        "agent_id": agent_id,
        "version_id": inteiro_positivo("version_id"),
        "playground": bool(dados.get("playground")),
        "max_seconds": inteiro_positivo("max_seconds"),
        # M4.3.2: ligação de saída originada pelo discador do RAPIA
        "saida": dados.get("direction") == "outbound",
        "motivo": (dados.get("motivo") or "").strip(),
    }


async def espera_atendimento(ctx: JobContext, limite: float) -> bool:
    """Ligação de saída: o agente entra na sala enquanto o celular ainda toca.
    Só abre a sessão com o Gemini quando o participante SIP fica com
    sip.callStatus = active (o paciente atendeu); antes disso o modelo ouviria
    o toque e falaria sozinho. False = desligou/recusou ou passou do limite."""
    await ctx.connect()
    atendeu = asyncio.Event()
    resultado = {"ok": False}

    def eh_sip(p: Any) -> bool:
        return "sip.callStatus" in p.attributes

    def confere(p: Any) -> None:
        if eh_sip(p) and p.attributes.get("sip.callStatus") == "active":
            resultado["ok"] = True
            atendeu.set()

    def saiu(p: Any) -> None:
        if eh_sip(p):
            atendeu.set()

    def mudou(_changed: dict[str, str], p: Any) -> None:
        confere(p)

    ctx.room.on("participant_connected", confere)
    ctx.room.on("participant_attributes_changed", mudou)
    ctx.room.on("participant_disconnected", saiu)
    try:
        for p in ctx.room.remote_participants.values():
            confere(p)
        await asyncio.wait_for(atendeu.wait(), timeout=limite)
    except asyncio.TimeoutError:
        pass
    finally:
        ctx.room.off("participant_connected", confere)
        ctx.room.off("participant_attributes_changed", mudou)
        ctx.room.off("participant_disconnected", saiu)
    return resultado["ok"]


async def busca_runtime(agent_id: int, version_id: int | None = None) -> dict[str, Any]:
    url = f"{RAPIA_API_URL}/voice/agents/{agent_id}/runtime"
    params = {"version": version_id} if version_id else None
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as sessao:
        async with sessao.get(url, params=params, headers={"x-api-key": RAPIA_API_TOKEN}) as resp:
            status = resp.status
            corpo = await resp.json(content_type=None)

    if status != 200 or not corpo.get("status"):
        raise RuntimeError(f"RAPIA recusou o runtime do agente {agent_id} versão {version_id or 'publicada'} (HTTP {status}): {corpo}")

    return corpo["data"]


def construir_tool(tool_def: dict[str, Any], room: str, turno: dict[str, int], version_id: int | None, ao_resultado=None):
    """Constrói uma function_tool "crua" (raw_schema) a partir da definição
    vinda do RAPIA — não há mais um método fixo por tool no worker (M1). Cada
    chamada do modelo vira um POST /voice/worker/tools/{name}; o RAPIA valida,
    persiste e devolve o resultado, que volta pro modelo como retorno da tool.
    """
    nome = tool_def["name"]
    raw_schema = {
        "name": nome,
        "description": tool_def.get("description") or "",
        "parameters": tool_def.get("parameters_schema") or {"type": "object", "properties": {}},
    }

    async def _executa(raw_arguments: dict[str, Any]) -> Any:
        corpo = dict(raw_arguments)
        corpo["room"] = room
        corpo["turn_seq"] = turno["seq"]
        if version_id:
            # a versão que este worker carregou: é assim que o RAPIA acha as
            # tools HTTP (definidas por versão no Estúdio) sem adivinhar
            corpo["version_id"] = version_id

        _log_coleta(nome, corpo)

        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as sessao:
            async with sessao.post(
                f"{RAPIA_API_URL}/voice/worker/tools/{nome}",
                json=corpo,
                headers={"x-api-key": RAPIA_API_TOKEN},
            ) as resp:
                dados = await resp.json(content_type=None)

        if not dados.get("status"):
            raise ToolError(dados.get("message") or f"Falha ao executar a ferramenta {nome}.")

        logger.info("TOOL %s -> %s", nome, json.dumps(dados.get("data"), ensure_ascii=False))
        if ao_resultado:
            ao_resultado(nome, dados.get("data"))
        return dados.get("data")

    return function_tool(_executa, raw_schema=raw_schema)


AVISO_LIMITE_S = float(os.getenv("VOICE_LIMITE_AVISO_S", "60"))


async def _fala_limitada(session: AgentSession, instrucoes: str, timeout: float = 15.0) -> None:
    """generate_reply com tempo máximo: fala interrompida pode nunca resolver o handle e travar o prazo."""
    try:
        await asyncio.wait_for(session.generate_reply(instructions=instrucoes).wait_for_playout(), timeout)
    except asyncio.TimeoutError:
        logger.warning("Limite da ligação: fala não terminou em %ss; seguindo", timeout)


async def _limite_da_ligacao(ctx: JobContext, session: AgentSession, runtime: dict[str, Any],
                             turno: dict[str, int], espera: dict[str, bool], limite: int) -> None:
    sala = ctx.room.name
    t0 = time.monotonic()
    try:
        await asyncio.sleep(max(limite - AVISO_LIMITE_S, limite / 2))
        if espera["transferida"]:
            return  # já está na fila: a IA não fala mais
        logger.info("Limite da ligação: aviso | sala=%s limite=%ss", sala, limite)
        await publica_evento(sala, "ai_limite_tempo", {"fase": "aviso", "limite_s": limite}, turno["seq"])
        await _fala_limitada(session, (
            "O tempo desta ligação está acabando. Em UMA frase curta, avise o paciente que vai encaminhá-lo "
            "para um atendente para continuar. Não repita dados nem faça novas perguntas."))

        await asyncio.sleep(max(0.0, limite - (time.monotonic() - t0)))  # prazo total contado desde o início
        if espera["transferida"]:
            return
        corpo = {"room": sala, "turn_seq": turno["seq"]}
        if runtime.get("agent_version_id"):
            corpo["version_id"] = runtime["agent_version_id"]
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as http:
            async with http.post(f"{RAPIA_API_URL}/voice/worker/tools/transferir_para_atendente", json=corpo,
                                 headers={"x-api-key": RAPIA_API_TOKEN}) as resp:
                dados = await resp.json(content_type=None)
        ok = bool((dados.get("data") or {}).get("ok")) if dados.get("status") else False
        logger.info("Limite da ligação: transferência %s | sala=%s", "aceita" if ok else "sem atendente", sala)
        await publica_evento(sala, "ai_limite_tempo", {"fase": "transferida" if ok else "encerrada", "limite_s": limite}, turno["seq"])
        if ok:
            espera["transferida"] = True  # o handler de estado silencia o agente depois da fala
            await _fala_limitada(session, (
                "Diga em uma frase curta que o paciente será atendido em instantes por um atendente e peça para aguardar. Depois não fale mais."))
        else:
            await _fala_limitada(session, (
                "O tempo da ligação acabou e não há atendente disponível. Em uma frase curta, agradeça, diga que a clínica "
                "retornará o contato e se despeça."))
            await asyncio.sleep(1.5)
            ctx.delete_room()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Limite da ligação: falha | sala=%s", sala)


def _log_coleta(nome: str, dados: dict[str, Any]) -> None:
    linha = {
        "tool": nome,
        "argumentos": dados,
        "logado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    with REGISTROS.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(linha, ensure_ascii=False) + "\n")


async def publica_transcricao(room: str, role: str, texto: str, turn_seq: int) -> None:
    """Fire-and-forget: chamado via asyncio.create_task, nunca aguardado pelo
    fluxo de áudio. Erro aqui não pode travar nem derrubar a ligação."""
    papel = PAPEL_TRANSCRICAO.get(role)
    if not papel:
        return
    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as sessao:
            async with sessao.post(
                f"{RAPIA_API_URL}/voice/worker/transcript",
                json={"room": room, "role": papel, "text": texto, "turn_seq": turn_seq},
                headers={"x-api-key": RAPIA_API_TOKEN},
            ) as resp:
                if resp.status != 200:
                    logger.warning("Falha ao publicar transcrição (HTTP %s)", resp.status)
    except Exception:
        logger.exception("Erro ao publicar transcrição no RAPIA")


async def publica_evento(room: str, tipo: str, payload: dict[str, Any], turn_seq: int) -> None:
    """Evento genérico (POST /voice/worker/event): grava em voice_call_events, ou
    no buffer Redis do Playground em sala pg-*. Mesmo cuidado da transcrição:
    erro aqui nunca derruba a ligação."""
    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as sessao:
            async with sessao.post(
                f"{RAPIA_API_URL}/voice/worker/event",
                json={"room": room, "type": tipo, "payload": payload, "turn_seq": turn_seq},
                headers={"x-api-key": RAPIA_API_TOKEN},
            ) as resp:
                if resp.status != 200:
                    logger.warning("Falha ao publicar evento %s (HTTP %s)", tipo, resp.status)
    except Exception:
        logger.exception("Erro ao publicar evento %s no RAPIA", tipo)


def modo_qualidade(runtime: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """M4.4: modo da guarda de qualidade (off | sombra | ativo) vindo da versão do
    agente. VOICE_QUALITY_GUARD_FORCAR (só na homologação) sobrepõe a versão: é
    como as ligações de calibração ficam em sombra sem publicar versão nova."""
    cfg = runtime.get("quality_guard") or {}
    modo, origem = cfg.get("mode") or "off", "versao"
    forcado = os.getenv("VOICE_QUALITY_GUARD_FORCAR", "").strip().lower()
    if forcado in ("off", "sombra", "ativo"):
        modo, origem = forcado, "env"
    if modo == "ativo":
        logger.warning("quality_guard=ativo ainda não transfere (M4.4 fase 1): funcionando como sombra")
    return modo, origem, cfg


class GuardaQualidade:
    """M4.4 fase 1 (sombra): assina a trilha de áudio do paciente (participante
    SIP, ou o navegador no Playground) num rtc.AudioStream próprio, em paralelo
    ao que a sessão do Gemini recebe, mede com qualidade.py e publica
    `audio_quality` a cada janela de 10 s e `audio_quality_summary` no fim.
    Só mede: nunca transfere nem fala nada na ligação."""

    TAXA = 16000

    def __init__(self, ctx: JobContext, turno: dict[str, int], modo: str, origem: str, cfg: dict[str, Any]) -> None:
        self.ctx = ctx
        self.turno = turno
        self.modo = modo
        self.origem = origem
        self.medidor = MedidorQualidade(self.TAXA)
        self.resumo = ResumoQualidade(
            float(cfg.get("snr_min_db", 10)), int(cfg.get("janelas_seguidas", 2)), float(cfg.get("max_buracos_pct", 5))
        )
        self.compreensao = ContadorCompreensao(int(cfg.get("max_incompreensoes", 2)))
        self.participante: str | None = None
        self._stream: rtc.AudioStream | None = None
        self._tarefa: asyncio.Task[None] | None = None
        self._cpu_medicao = 0.0
        self._cpu0 = time.process_time()
        self._t0 = time.monotonic()

    def comeca(self) -> None:
        self.ctx.room.on("track_subscribed", self._assinada)
        for p in self.ctx.room.remote_participants.values():
            for pub in p.track_publications.values():
                if pub.track is not None:
                    self._assinada(pub.track, pub, p)

    def _assinada(self, track: rtc.Track, _pub: Any, participante: rtc.RemoteParticipant) -> None:
        if self._tarefa is not None or track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if participante.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            return
        self.participante = participante.identity
        self._stream = rtc.AudioStream.from_track(track=track, sample_rate=self.TAXA, num_channels=1)
        self._tarefa = asyncio.create_task(self._le())
        logger.info("Qualidade: medindo o áudio de %s (modo %s, origem %s)", participante.identity, self.modo, self.origem)

    async def _le(self) -> None:
        assert self._stream is not None
        async for ev in self._stream:
            t = time.thread_time()
            prontas = self.medidor.alimenta(np.frombuffer(ev.frame.data, dtype=np.int16))
            self._cpu_medicao += time.thread_time() - t
            for m in prontas:
                asyncio.create_task(self._publica(m))

    async def _publica(self, m: dict[str, Any]) -> None:
        m.update(self.resumo.adiciona(m))
        m["modo"] = self.modo
        logger.info(
            "audio_quality #%s | SNR %s dB, fala %s dBFS (%s%%), ruído %s dBFS, clip %s%%, buracos %s (%s%%)%s",
            m["janela"], m["snr_db"], m["fala_dbfs"], m["fala_pct"], m["ruido_dbfs"], m["clipping_pct"],
            m["buracos_qtd"], m["buracos_pct"], f" | ruim: {','.join(m['motivos'])}" if m["motivos"] else "",
        )
        await publica_evento(self.ctx.room.name, "audio_quality", m, self.turno["seq"])

    def fala(self, role: str, texto: str | None) -> None:
        """Cada fala transcrita (paciente ou IA) passa pelo contador de
        compreensão; incompreensão vira evento comprehension_miss (só registro)."""
        if role == "user":
            evento = self.compreensao.fala_paciente(texto)
        elif role == "assistant":
            evento = self.compreensao.fala_ia(texto)
        else:
            return
        if evento is None:
            return
        evento["modo"] = self.modo
        logger.info(
            "comprehension_miss | incidente %s%s, %s seguidas (%s) | paciente: %r | IA: %r",
            evento["incidente"], " (mesclado)" if evento["mesclado"] else "", evento["seguidas"],
            ",".join(evento["motivos"]), (evento["texto_paciente"] or "")[:80], (evento["texto_ia"] or "")[:80],
        )
        asyncio.create_task(publica_evento(self.ctx.room.name, "comprehension_miss", evento, self.turno["seq"]))

    async def encerra(self) -> None:
        if self._tarefa is not None:
            self._tarefa.cancel()
        if self._stream is not None:
            await self._stream.aclose()
        ultima = self.medidor.fecha()
        if ultima:
            await self._publica(ultima)
        dur = time.monotonic() - self._t0
        cpu_job = time.process_time() - self._cpu0
        payload = self.resumo.resumo()
        payload.update(self.compreensao.resumo())
        payload.update({
            "modo": self.modo,
            "origem": self.origem,
            "participante": self.participante,
            "sessao_s": round(dur, 1),
            # custo: CPU do PROCESSO durante a sessão e só da medição (thread do job).
            # No Windows os jobs são threads do mesmo processo do worker
            # (JobExecutorType.THREAD): com 2 sessões, o número do processo soma as duas.
            "cpu_processo_s": round(cpu_job, 2),
            "cpu_processo_pct_nucleo": round(100 * cpu_job / dur, 1) if dur else None,
            "cpu_medicao_ms": round(1000 * self._cpu_medicao, 1),
        })
        logger.info("audio_quality_summary | %s", json.dumps(payload, ensure_ascii=False))
        await publica_evento(self.ctx.room.name, "audio_quality_summary", payload, self.turno["seq"])


def transcricao_entrada_kwargs() -> dict[str, Any]:
    """M5.1/A2: o plugin usa AudioTranscriptionConfig() vazio = detecção automática de idioma,
    e com áudio de telefone (8 kHz) o paciente saiu transcrito como espanhol. Experimento por .env
    (sem variável = comportamento de sempre): VOICE_TRANSCRICAO_IDIOMAS (ex.: pt-BR, dica de idioma
    da transcrição de entrada) e VOICE_TRANSCRICAO_VOCAB (frases separadas por |, viés do ASR)."""
    idiomas = [i.strip() for i in os.getenv("VOICE_TRANSCRICAO_IDIOMAS", "").split(",") if i.strip()]
    vocab = [v.strip() for v in os.getenv("VOICE_TRANSCRICAO_VOCAB", "").split("|") if v.strip()]
    if not idiomas and not vocab:
        return {}
    cfg = types.AudioTranscriptionConfig(language_codes=idiomas or None, custom_vocabulary=vocab or None)
    logger.info("transcricao_entrada | idiomas=%s vocab=%d", idiomas, len(vocab))
    return {"input_audio_transcription": cfg}


def realtime_input_config() -> "types.RealtimeInputConfig":
    """Sensibilidade de início/fim de fala do Gemini Live — é o que controla o
    barge-in (o paciente falar por cima da IA). Configurável por .env para a
    calibração com ligação real de telefone (TODO-RAPIA-VOICE-V1.md, seção 7,
    revisão de 22/09/2026) não exigir mudar código: só trocar
    VOICE_START_SENSITIVITY / VOICE_END_SENSITIVITY (HIGH ou LOW) e reiniciar o
    worker. HIGH/HIGH é só o ponto de partida sugerido pela documentação do
    Gemini Live para barge-in responsivo — AINDA NÃO calibrado contra áudio real
    de telefone (8 kHz, ruído de linha). Pendência do M1 até testar com ligação
    real e documentar o valor escolhido.
    """
    inicio = getattr(types.StartSensitivity, f"START_SENSITIVITY_{os.getenv('VOICE_START_SENSITIVITY', 'HIGH')}")
    fim = getattr(types.EndSensitivity, f"END_SENSITIVITY_{os.getenv('VOICE_END_SENSITIVITY', 'HIGH')}")
    return types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            start_of_speech_sensitivity=inicio,
            end_of_speech_sensitivity=fim,
        )
    )


def _carga_do_worker() -> dict[str, Any]:
    """O worker informa ao LiveKit a CPU da MÁQUINA (0-1) como carga; com o PC da
    homologação perto de 1 (navegador, IDE...) o LiveKit deixa de despachar
    ("no servers available") e a ligação fica sem atendimento (M4.4, achado de
    26/09/2026). VOICE_WORKER_CARGA_FIXA (só na homologação) informa um valor
    fixo; sem a variável, vale o padrão do SDK."""
    bruto = os.getenv("VOICE_WORKER_CARGA_FIXA", "").strip()
    if not bruto:
        return {}
    valor = float(bruto)
    logger.warning("Carga do worker fixada em %s (VOICE_WORKER_CARGA_FIXA): o LiveKit não enxerga a CPU real", valor)
    return {"load_fnc": lambda: valor}


server = AgentServer(**_carga_do_worker())


@server.rtc_session(agent_name=os.getenv("AGENT_NAME", "rapia-voice"))
async def atender(ctx: JobContext) -> None:
    logger.info("Nova sessão | sala=%s", ctx.room.name)

    job = parametros_do_job(ctx)
    agent_id = job["agent_id"]
    runtime = await busca_runtime(agent_id, job["version_id"])
    logger.info(
        "Runtime carregado | agente=%s (id=%s) versão=%s (%s)%s",
        runtime.get("name"), agent_id, runtime.get("agent_version_id"), runtime.get("version_status"),
        " | PLAYGROUND" if job["playground"] else "",
    )

    # M5: qual agente/versão atendeu (voice_calls.agent_id; o resumo pós-chamada
    # segue a configuração desta versão)
    asyncio.create_task(publica_evento(ctx.room.name, "ai_session", {
        "agent_id": agent_id, "agent_version_id": runtime.get("agent_version_id"),
        "version_status": runtime.get("version_status"), "model": runtime.get("model"),
    }, 0))

    if job["saida"]:
        limite = float(os.getenv("OUTBOUND_ANSWER_TIMEOUT", "90"))
        if not await espera_atendimento(ctx, limite):
            logger.info("Saída: paciente não atendeu; encerrando | sala=%s", ctx.room.name)
            ctx.shutdown(reason="saida_nao_atendida")
            return
        logger.info("Saída: paciente atendeu | sala=%s", ctx.room.name)

    if job["playground"] and job["max_seconds"]:
        limite = job["max_seconds"]

        async def _corta_sessao() -> None:
            await asyncio.sleep(limite)
            logger.info("Playground: limite de %ss atingido; encerrando a sessão | sala=%s", limite, ctx.room.name)
            ctx.shutdown(reason="playground_max_seconds")

        cronometro = asyncio.create_task(_corta_sessao())

        async def _para_cronometro() -> None:
            cronometro.cancel()

        ctx.add_shutdown_callback(_para_cronometro)

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=runtime.get("model") or os.getenv("GEMINI_MODEL", "gemini-3.8-live"),
            voice=runtime.get("voice") or os.getenv("GEMINI_VOICE", "Kore"),
            # "or" trataria temperature=0.0 (válido, determinístico) como ausente
            temperature=float(runtime["temperature"]) if runtime.get("temperature") is not None else float(os.getenv("GEMINI_TEMPERATURE", "0.6")),
            # Sem idioma fixo, com áudio de telefone (8 kHz) o modelo chegou a
            # entender o paciente como espanhol ("¿Qué?") - ligação real de 25/09/2026.
            language=runtime.get("language") or os.getenv("GEMINI_LANGUAGE", "pt-BR"),
            api_key=os.getenv("GOOGLE_API_KEY"),
            realtime_input_config=realtime_input_config(),
            **transcricao_entrada_kwargs(),
        ),
    )

    # turn_seq: sequencial simples, incrementado a cada fala (do modelo ou do
    # paciente) que vira transcrição. Tools chamadas entre duas falas carregam
    # o turn_seq da última fala — é o que correlaciona, no mesmo número,
    # "nesta fala a IA chamou esta tool" entre voice_transcripts e
    # voice_call_events (ver comentário da migration de voice_call_events).
    turno = {"seq": 0}
    # M4.4: criada depois do session.start (precisa da sala); fica aqui para o
    # handler abaixo passar cada fala ao contador de compreensão
    qualidade: dict[str, GuardaQualidade | None] = {"guarda": None}

    @session.on("conversation_item_added")
    def _log_item(ev: Any) -> None:
        item = getattr(ev, "item", None)
        texto = getattr(item, "text_content", None) if item else None
        role = getattr(item, "role", "?") if item else "?"
        guarda = qualidade["guarda"]
        if not texto:
            # fala do paciente sem transcrição também é sinal de incompreensão
            if guarda and role == "user":
                guarda.fala(role, texto)
            return
        turno["seq"] += 1
        logger.info("[%s] %s", role, texto)
        asyncio.create_task(publica_transcricao(ctx.room.name, role, texto, turno["seq"]))
        if guarda:
            guarda.fala(role, texto)

    # M5: uso do Gemini (tokens por tipo) para o custo estimado. O SDK acumula por
    # modelo e emite session_usage_updated a cada resposta (usage_metadata do
    # Gemini); guardamos o último acumulado e mandamos UM evento ai_usage no fim.
    uso = {"ultimo": None, "respostas": 0, "t0": time.monotonic()}

    @session.on("session_usage_updated")
    def _uso(ev: Any) -> None:
        uso["ultimo"] = ev.usage
        uso["respostas"] += 1

    async def _envia_uso() -> None:
        atual = uso["ultimo"] or session.usage
        modelos = [m.model_dump() for m in (atual.model_usage if atual else [])]
        payload = {
            "modelos": modelos,
            "respostas": uso["respostas"],
            "sessao_s": round(time.monotonic() - uso["t0"], 1),
            "origem": "livekit-agents session_usage_updated",
        }
        logger.info("ai_usage | %s", json.dumps(payload, ensure_ascii=False))
        await publica_evento(ctx.room.name, "ai_usage", payload, turno["seq"])

    ctx.add_shutdown_callback(_envia_uso)

    # M5 (ligação real 125): transferida para a fila, a IA seguia ouvindo o paciente
    # e repetia os dados até a atendente assumir. Com a transferência aceita
    # (ok=true), depois da fala de espera o agente para de ouvir; sai da sala
    # quando a atendente entra (_humano_entrou). Sem atendente (ok=false) nada muda.
    espera = {"transferida": False, "muda": False}

    def _ao_resultado(nome: str, dados: Any) -> None:
        if nome == "transferir_para_atendente" and isinstance(dados, dict) and dados.get("ok"):
            espera["transferida"] = True

    @session.on("agent_state_changed")
    def _estado(ev: Any) -> None:
        if espera["transferida"] and not espera["muda"] and ev.new_state == "listening":
            espera["muda"] = True
            session.input.set_audio_enabled(False)
            logger.info("Transferida para a fila: o agente parou de ouvir o paciente | sala=%s", ctx.room.name)
            asyncio.create_task(publica_evento(ctx.room.name, "ai_waiting", {"motivo": "aguardando_atendente"}, turno["seq"]))

    tools = [construir_tool(t, ctx.room.name, turno, runtime.get("agent_version_id"), _ao_resultado) for t in runtime.get("tools", [])]
    agente = Agent(instructions=runtime["prompt"], tools=tools)

    await session.start(agent=agente, room=ctx.room)

    # M5 (achado na ligação real 124, 27/09/2026): depois que a atendente assume
    # (participante user_*, token do VoiceTokenController) o agente continuava na
    # sala ouvindo o paciente e respondia por cima dela. Agora sai: encerra o job
    # (a sala continua: delete_room_on_close é False), o que dispara os shutdown
    # callbacks (uso do Gemini, resumo da qualidade) com o que houve até ali.
    def _humano_entrou(p: rtc.RemoteParticipant) -> None:
        if not p.identity.startswith("user_"):
            return
        logger.info("Atendente %s entrou: o agente sai da sala | sala=%s", p.identity, ctx.room.name)
        asyncio.create_task(publica_evento(ctx.room.name, "ai_left", {"motivo": "atendente_assumiu", "atendente": p.identity}, turno["seq"]))
        ctx.shutdown(reason="atendente_assumiu")

    ctx.room.on("participant_connected", _humano_entrou)
    for _p in list(ctx.room.remote_participants.values()):
        _humano_entrou(_p)

    # M5.1/A4: max_call_seconds da versão em ligação real (o Playground tem o limite próprio, acima).
    # Vale só enquanto a IA está na sala (o job acaba quando a atendente assume). Aviso antes do fim;
    # no limite tenta transferir para a fila e, sem atendente, se despede e encerra a sala.
    limite_ligacao = os.getenv("VOICE_MAX_CALL_SECONDS_FORCAR") or runtime.get("max_call_seconds")  # FORCAR: só p/ testar em homologação
    if limite_ligacao and not job["playground"]:
        asyncio.create_task(_limite_da_ligacao(ctx, session, runtime, turno, espera, int(limite_ligacao)))

    modo, origem, cfg_qualidade = modo_qualidade(runtime)
    if modo != "off":
        guarda = GuardaQualidade(ctx, turno, modo, origem, cfg_qualidade)
        guarda.comeca()
        qualidade["guarda"] = guarda
        ctx.add_shutdown_callback(guarda.encerra)

    if job["saida"]:
        # A saudação do agente é escrita para quem LIGA para a clínica; aqui é
        # a clínica que liga. O prompt continua o mesmo.
        saudacao = (
            "Esta é uma ligação feita PELA clínica para o paciente, que acabou de atender. "
            "Cumprimente, diga o nome da clínica, informe que a ligação pode ser gravada "
            "para fins de atendimento e confirme o nome de quem atendeu."
            + (f" Motivo da ligação, a explicar depois da confirmação: {job['motivo']}" if job["motivo"] else "")
        )
    else:
        saudacao = runtime.get("greeting_instructions") or (
            "Cumprimente o paciente, diga o nome da clínica, informe que a ligação "
            "pode ser gravada para fins de atendimento e pergunte o nome completo dele."
        )
    await session.generate_reply(instructions=saudacao)


if __name__ == "__main__":
    agents.cli.run_app(server)
