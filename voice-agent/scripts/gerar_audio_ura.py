"""Gera o prompt de áudio da URA (ura-boas-vindas.wav) com a voz do Gemini Live.

Reaproveita o gerar() de gerar_amostras_voz.py (mesmo modelo e chave do .env) e
converte a saída (PCM 24 kHz) para o formato que o Asterisk toca sem transcodificar
pesado: WAV 8 kHz, mono, 16-bit. Confere o que foi dito pela transcrição da saída.

Rodar (da pasta voice-agent):
  .venv\\Scripts\\python.exe scripts\\gerar_audio_ura.py --saida ..\\livekit-ec2\\sounds\\ura-boas-vindas.wav
  (opcional: --voz Leda  --texto "...")
Depois: copiar para a EC2 (~/livekit-ec2/sounds/) e para livekit-local/config/asterisk/sounds/custom/.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_amostras_voz as base  # noqa: E402

# Opções atuais da URA (voice_ura_options do tronco +558431901994, 25/09/2026):
# 1 = agente de IA, 2 = fila humana, sem dígito = fila padrão (humana).
TEXTO = (
    "Olá! Você ligou para a Clínica Coopab. "
    "Para falar com a nossa assistente virtual, digite 1. "
    "Para falar com um atendente, digite 2. "
    "Ou, se preferir, aguarde na linha que você será atendido."
)


async def principal() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True, help="caminho do .wav de destino")
    ap.add_argument("--voz", default="Leda")
    ap.add_argument("--texto", default=TEXTO)
    args = ap.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY ausente no .env")
        return 1
    if not shutil.which("ffmpeg"):
        print("ffmpeg não encontrado no PATH")
        return 1

    base.FRASE = args.texto
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.8-live")
    cliente = base.genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    try:
        pcm, dito, uso = await base.gerar(cliente, modelo, args.voz)
    except Exception as e:  # mostra o tipo/mensagem, nunca a chave
        print(f"[FALHA] {type(e).__name__}: {str(e)[:300]}")
        return 1
    segundos = len(pcm) / 2 / base.TAXA
    if segundos < 3:
        print(f"[FALHA] áudio curto demais ({segundos:.1f}s)")
        return 1

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        bruto = Path(tmp) / "bruto.wav"
        with wave.open(str(bruto), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(base.TAXA)
            w.writeframes(pcm)
        # passa-baixa antes de reamostrar (evita aliasing) e meio segundo de silêncio no início
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto),
             "-af", "lowpass=f=3400,adelay=500,aresample=8000:resampler=soxr",
             "-ar", "8000", "-ac", "1", "-sample_fmt", "s16", str(destino)],
            check=True,
        )
    print(f"[ok] voz={args.voz} modelo={modelo} {segundos:.1f}s -> {destino}")
    print(f"     tokens entrada={uso.get('entrada')} saída={uso.get('saida')}")
    print(f"     dito: {dito}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(principal()))
