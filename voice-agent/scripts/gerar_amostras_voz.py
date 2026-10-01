"""Gera as amostras de pré-escuta do seletor de voz do Estúdio (M3 E6).

Usa o mesmo modelo Live da ligação (GEMINI_MODEL do .env) e a mesma chave, com
uma frase fixa de clínica em pt-BR, uma voz por vez. Grava um WAV temporário por
voz e converte para mp3 com o ffmpeg em <saida>/<Voz>.mp3. Confere o que foi dito
pela transcrição da própria saída (não dá para "ouvir" aqui) e imprime os tokens
usados em cada chamada (para estimar o custo).

Rodar (da pasta voice-agent):
  .venv\\Scripts\\python.exe scripts\\gerar_amostras_voz.py --saida ..\\..\\sysweb\\static\\assets\\audio\\voz
  .venv\\Scripts\\python.exe scripts\\gerar_amostras_voz.py --voz Kore --saida <pasta>   # uma só
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

VOZES = ["Kore", "Puck", "Charon", "Aoede", "Fenrir", "Leda", "Orus", "Zephyr"]
FRASE = (
    "Olá, aqui é a assistente virtual da clínica. Como posso ajudar você hoje? "
    "Posso agendar uma consulta ou informar o horário de atendimento."
)
INSTRUCAO = (
    "Você é um leitor de texto. Diga exatamente o texto que o usuário enviar, em português do Brasil, "
    "com tom acolhedor de atendimento de clínica, sem acrescentar, resumir nem comentar nada."
)
TAXA = 24000  # o Gemini Live devolve PCM 16-bit mono a 24 kHz


async def gerar(cliente: genai.Client, modelo: str, voz: str) -> tuple[bytes, str, dict]:
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=INSTRUCAO,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voz)),
            language_code="pt-BR",
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    pcm = bytearray()
    transcricao = ""
    uso: dict = {}
    async with cliente.aio.live.connect(model=modelo, config=config) as sessao:
        await sessao.send_realtime_input(text=FRASE)
        async for msg in sessao.receive():
            sc = msg.server_content
            if sc:
                if sc.model_turn:
                    for parte in sc.model_turn.parts or []:
                        if parte.inline_data and parte.inline_data.data:
                            pcm.extend(parte.inline_data.data)
                if sc.output_transcription and sc.output_transcription.text:
                    transcricao += sc.output_transcription.text
            if msg.usage_metadata:
                u = msg.usage_metadata
                uso = {
                    "entrada": u.prompt_token_count or 0,
                    "saida": u.response_token_count or 0,
                    "total": u.total_token_count or 0,
                    "detalhe_saida": [(d.modality.name if d.modality else "?", d.token_count) for d in (u.response_tokens_details or [])],
                }
            if sc and sc.turn_complete:
                break
    return bytes(pcm), transcricao.strip(), uso


def salvar_mp3(pcm: bytes, destino: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "amostra.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(TAXA)
            w.writeframes(pcm)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "48k", "-ac", "1", str(destino)],
            check=True,
        )


async def principal() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voz", help="gera só esta voz")
    ap.add_argument("--saida", required=True, help="pasta de destino dos mp3")
    args = ap.parse_args()

    chave = os.getenv("GOOGLE_API_KEY")
    if not chave:
        print("GOOGLE_API_KEY ausente no .env")
        return 1
    if not shutil.which("ffmpeg"):
        print("ffmpeg não encontrado no PATH")
        return 1

    modelo = os.getenv("GEMINI_MODEL", "gemini-3.8-live")
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    vozes = [args.voz] if args.voz else VOZES
    cliente = genai.Client(api_key=chave)

    print(f"modelo={modelo} | {len(vozes)} voz(es) | saída={saida}")
    falhas = 0
    tot_in = tot_out = 0
    for voz in vozes:
        try:
            pcm, texto, uso = await gerar(cliente, modelo, voz)
        except Exception as e:  # mostra o tipo/mensagem, nunca a chave
            print(f"[FALHA] {voz}: {type(e).__name__}: {str(e)[:300]}")
            falhas += 1
            continue
        segundos = len(pcm) / 2 / TAXA
        if segundos < 2:
            print(f"[FALHA] {voz}: áudio curto demais ({segundos:.1f}s)")
            falhas += 1
            continue
        salvar_mp3(pcm, saida / f"{voz}.mp3")
        tot_in += uso.get("entrada", 0)
        tot_out += uso.get("saida", 0)
        print(f"[ok] {voz}: {segundos:.1f}s | tokens entrada={uso.get('entrada')} saída={uso.get('saida')} {uso.get('detalhe_saida')}")
        print(f"     dito: {texto}")
    print(f"TOTAL tokens entrada={tot_in} saída={tot_out} | falhas={falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(principal()))
