"""Frases fixas do worker (aviso/encerramento por limite de tempo), faladas SEM passar pelo prompt do agente.

Por quê (ligação 143, 05/10/2026): pedir ao Gemini Live "diga X" com generate_reply(instructions=...) manda o texto como
um turno de modelo + um "." de usuário; no meio de uma conversa o modelo ficou mudo no aviso e, no encerramento, LEU o
próprio prompt em voz alta. Aqui a frase é sintetizada UMA vez (sessão Live separada, só leitura de texto, sem o prompt do
agente, com a voz do agente) e guardada em disco; na ligação é tocada com session.say(audio=...), sem nenhum LLM no caminho.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import AsyncIterator

from google import genai
from google.genai import types
from livekit import rtc

logger = logging.getLogger("frases_fixas")

TAXA = 24000  # o Gemini Live devolve PCM 16-bit mono a 24 kHz
PASTA = Path(__file__).resolve().parent / "cache_frases"
INSTRUCAO_LEITOR = (
    "Você é um leitor de texto. Diga exatamente o texto que o usuário enviar, em português do Brasil, "
    "com tom acolhedor de atendimento de clínica, sem acrescentar, resumir nem comentar nada."
)


def _arquivo(voz: str, texto: str) -> Path:
    h = hashlib.sha1(f"{voz}|{texto}".encode("utf-8")).hexdigest()[:16]
    return PASTA / f"{voz}_{h}.pcm"


async def sintetiza(voz: str, texto: str, timeout: float = 25.0) -> bytes | None:
    """PCM 24 kHz mono da frase na voz dada (com cache em disco). None se não conseguiu."""
    arq = _arquivo(voz, texto)
    if arq.exists() and arq.stat().st_size > 4800:
        return arq.read_bytes()
    chave = os.getenv("GOOGLE_API_KEY")
    if not chave:
        return None
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.8-live")
    cfg = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=INSTRUCAO_LEITOR,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voz)),
            language_code="pt-BR",
        ),
    )

    async def _gera() -> bytes:
        pcm = bytearray()
        async with genai.Client(api_key=chave).aio.live.connect(model=modelo, config=cfg) as sessao:
            await sessao.send_realtime_input(text=texto)
            async for msg in sessao.receive():
                sc = msg.server_content
                if sc and sc.model_turn:
                    for parte in sc.model_turn.parts or []:
                        if parte.inline_data and parte.inline_data.data:
                            pcm.extend(parte.inline_data.data)
                if sc and sc.turn_complete:
                    break
        return bytes(pcm)

    try:
        pcm = await asyncio.wait_for(_gera(), timeout)
    except Exception as exc:  # noqa: BLE001 - sem a frase fixa o worker usa o plano B
        logger.warning("Frase fixa não sintetizada (%s): %s", voz, exc)
        return None
    if len(pcm) < 4800:  # < 0,1 s: veio vazio
        return None
    PASTA.mkdir(exist_ok=True)
    arq.write_bytes(pcm)
    logger.info("Frase fixa sintetizada | voz=%s bytes=%d", voz, len(pcm))
    return pcm


async def quadros(pcm: bytes, ms: int = 100) -> AsyncIterator[rtc.AudioFrame]:
    """PCM -> AudioFrames para session.say(audio=...)."""
    amostras = TAXA * ms // 1000
    passo = amostras * 2
    for i in range(0, len(pcm), passo):
        parte = pcm[i:i + passo]
        parte = parte[: len(parte) - (len(parte) % 2)]
        if not parte:
            continue
        yield rtc.AudioFrame(data=parte, sample_rate=TAXA, num_channels=1, samples_per_channel=len(parte) // 2)
