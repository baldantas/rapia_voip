"""Música instrumental de espera (paciente na fila, IA calada, esperando a atendente assumir).

A faixa vem de `audio/espera.wav` (WAV PCM 16 bits, qualquer taxa; coloque a sua, com direito de uso) ou, se não existir,
é GERADA aqui (pad suave em Lá menor, sem direitos autorais) e guardada em `audio/espera_gerada.wav`. É tocada em laço
direto na saída de áudio da sessão (como as frases fixas), em volume baixo, até a atendente entrar e o job acabar.
"""

from __future__ import annotations

import asyncio
import logging
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np
from livekit import rtc

logger = logging.getLogger("musica_espera")

TAXA = 24000
PASTA = Path(__file__).resolve().parent / "audio"
_cache: dict[str, np.ndarray] = {}


def _gera() -> np.ndarray:
    """~24 s: Am - F - C - G, cada acorde 6 s, pad com leve vibrato e notas de sino suaves; início e fim em fade para o laço."""
    acordes = [
        (220.00, 261.63, 329.63),  # Am
        (174.61, 220.00, 261.63),  # F
        (261.63, 329.63, 392.00),  # C
        (196.00, 246.94, 293.66),  # G
    ]
    dur = 6.0
    n = int(TAXA * dur)
    t = np.arange(n) / TAXA
    saida = []
    for i, notas in enumerate(acordes):
        env = np.minimum(1.0, np.minimum(t / 1.2, (dur - t) / 1.2)) ** 1.5
        pad = np.zeros(n)
        for j, f in enumerate(notas):
            vib = 1 + 0.002 * np.sin(2 * np.pi * (0.25 + 0.05 * j) * t)
            pad += np.sin(2 * np.pi * f * vib * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
        pad *= env / (len(notas) * 1.25)
        # notas de sino (arpejo lento): uma a cada 1,5 s, na oitava de cima, com decaimento
        sino = np.zeros(n)
        for k, f in enumerate((notas[0], notas[1], notas[2], notas[1])):
            ini = int(k * 1.5 * TAXA)
            m = n - ini
            tt = np.arange(m) / TAXA
            sino[ini:] += np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 2.2) * 0.22
        saida.append(pad * 0.9 + sino)
    x = np.concatenate(saida)
    ponta = int(TAXA * 0.5)
    x[:ponta] *= np.linspace(0, 1, ponta)
    x[-ponta:] *= np.linspace(1, 0, ponta)
    pico = float(np.max(np.abs(x))) or 1.0
    return (x / pico).astype(np.float32)


def _le_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho), "rb") as w:
        taxa, canais, largura = w.getframerate(), w.getnchannels(), w.getsampwidth()
        dados = w.readframes(w.getnframes())
    if largura != 2:
        raise ValueError("use WAV PCM de 16 bits")
    x = np.frombuffer(dados, dtype=np.int16).astype(np.float32) / 32768.0
    if canais > 1:
        x = x.reshape(-1, canais).mean(axis=1)
    if taxa != TAXA:
        alvo = int(len(x) * TAXA / taxa)
        x = np.interp(np.linspace(0, len(x) - 1, alvo), np.arange(len(x)), x).astype(np.float32)
    return x


def faixa() -> np.ndarray:
    """Faixa em float32 mono 24 kHz, normalizada para pico 1.0."""
    if "x" in _cache:
        return _cache["x"]
    usuario = PASTA / "espera.wav"
    if usuario.exists():
        x = _le_wav(usuario)
        logger.info("Música de espera: %s (%.1f s)", usuario.name, len(x) / TAXA)
    else:
        x = _gera()
        PASTA.mkdir(exist_ok=True)
        with wave.open(str(PASTA / "espera_gerada.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(TAXA)
            w.writeframes((x * 32767 * 0.8).astype(np.int16).tobytes())
        logger.info("Música de espera gerada (%.1f s)", len(x) / TAXA)
    pico = float(np.max(np.abs(x))) or 1.0
    _cache["x"] = (x / pico).astype(np.float32)
    return _cache["x"]


async def toca_em_laco(session: Any, ganho: float = 0.3, ms: int = 100) -> None:
    """Toca a faixa em laço na saída de áudio da sessão, no ritmo do tempo real. Cancelar a tarefa para parar."""
    saida = session.output.audio
    if saida is None:
        return
    x = (faixa() * ganho * 32767).astype(np.int16)
    taxa = saida.sample_rate or TAXA
    rebobina = None if taxa == TAXA else rtc.AudioResampler(TAXA, taxa, num_channels=1)
    passo = TAXA * ms // 1000
    inicio = time.monotonic()
    enviado = 0.0
    i = 0
    try:
        while True:
            pedaco = x[i:i + passo]
            if len(pedaco) < passo:  # fim da faixa: emenda com o começo
                pedaco = np.concatenate([pedaco, x[:passo - len(pedaco)]])
            i = (i + passo) % len(x)
            quadro = rtc.AudioFrame(data=pedaco.tobytes(), sample_rate=TAXA, num_channels=1, samples_per_channel=len(pedaco))
            for q in (rebobina.push(quadro.data) if rebobina else [quadro]):
                await saida.capture_frame(q)
            enviado += ms / 1000
            # mantém ~0,5 s à frente do relógio: o buffer não cresce e parar é rápido
            adiantado = enviado - (time.monotonic() - inicio) - 0.5
            if adiantado > 0:
                await asyncio.sleep(adiantado)
    except asyncio.CancelledError:
        try:
            saida.clear_buffer()
        except Exception:
            pass
        raise
