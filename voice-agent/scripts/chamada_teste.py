"""Ligação de TESTE sem telefone (M5): uma voice_calls "de verdade" pelo caminho real.

Diferente do Playground (sala pg-*, que não cria voice_calls), este script:
  1. cria a sala `call-api_{numero}_{12 aleatórios}` no LiveKit (API de servidor,
     mesma URL/chaves do worker) -> webhook room_started real -> voice_calls;
  2. despacha o agente `rapia-voice` com {"agent_id": N} (versão PUBLICADA, como
     numa ligação real) -> status `ai`, transcrições e eventos em voice_*;
  3. entra na sala como "paciente" (identity teste_paciente, não é SIP nem
     user_*) e FALA o roteiro com o TTS local (mesmas falas do playground_smoke);
  4. segura a ligação N segundos (--segurar) para dar tempo de olhar o Painel 360;
  5. sai e apaga a sala (DeleteRoom) -> room_finished real -> encerraChamada.

Número padrão 849990000NN (faixa fictícia, a mesma da massa de demonstração).
Não passa pelo filtro de entrada nem pela URA (isso é do Asterisk).
A chamada fica no banco: remova com --remover SALA ou pelo script da massa.

Uso (na pasta voice-agent):
  .venv\\Scripts\\python.exe scripts\\chamada_teste.py --roteiro full --segurar 20
  .venv\\Scripts\\python.exe scripts\\chamada_teste.py --remover call-api_84999000001_XXXXXXXXXXXX
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import random
import string
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from livekit import rtc

sys.path.insert(0, str(Path(__file__).resolve().parent))
import playground_smoke as ps  # noqa: E402

ENV: dict[str, str] = {}
for _linha in (ps.BASE / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in _linha and not _linha.lstrip().startswith("#"):
        _k, _v = _linha.split("=", 1)
        ENV[_k.strip()] = _v.strip()

HTTP_LK = ENV.get("LIVEKIT_URL", "ws://localhost:7880").replace("ws", "http", 1)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwt(claims: dict, ttl: int = 300) -> str:
    agora = int(time.time())
    corpo = {"iss": ENV["LIVEKIT_API_KEY"], "nbf": agora - 10, "exp": agora + ttl}
    corpo.update(claims)
    cab = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    cor = _b64(json.dumps(corpo).encode())
    sig = hmac.new(ENV["LIVEKIT_API_SECRET"].encode(), f"{cab}.{cor}".encode(), hashlib.sha256).digest()
    return f"{cab}.{cor}.{_b64(sig)}"


def twirp(servico: str, metodo: str, corpo: dict, sala: str) -> dict:
    token = jwt({"sub": "chamada-teste", "video": {"roomCreate": True, "roomAdmin": True, "roomList": True, "room": sala}})
    req = urllib.request.Request(
        f"{HTTP_LK}/twirp/livekit.{servico}/{metodo}", data=json.dumps(corpo).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read() or b"{}")


def estado_no_rapia(sala: str) -> dict:
    return ps.tinker(
        f"$c = DB::table('voice_calls')->where('room_name','{sala}')->first();"
        "$o = $c ? ['id'=>$c->id,'status'=>$c->status,'duration'=>$c->duration_seconds,"
        "'transcripts'=>DB::table('voice_transcripts')->where('call_id',$c->id)->count(),"
        "'events'=>DB::table('voice_call_events')->where('call_id',$c->id)->pluck('type')] : null;"
        "echo '@@'.json_encode($o).'@@';"
    )


def remover(sala: str) -> None:
    print(ps.tinker(
        f"$c = DB::table('voice_calls')->where('room_name','{sala}')->where('room_name','like','call-api_849990000%')->first();"
        "if ($c) { foreach (DB::table('voice_recordings')->where('call_id',$c->id)->pluck('s3_key') as $k)"
        " { if ($k) { \\Storage::disk('voz_gravacoes')->delete($k); } }"
        " foreach (['voice_transcripts','voice_call_events','voice_queue_entries','voice_recordings'] as $t)"
        " { DB::table($t)->where('call_id',$c->id)->delete(); } DB::table('voice_calls')->where('id',$c->id)->delete(); }"
        "echo '@@'.json_encode(['removida'=>(bool)$c]).'@@';"
    ))


async def executa(args) -> int:
    aleatorio = "".join(random.choices(string.ascii_letters + string.digits, k=12))
    sala = f"call-api_{args.numero}_{aleatorio}"
    print(f"sala: {sala}", flush=True)

    roteiro = {"quick": ps.ROTEIRO_QUICK, "full": ps.ROTEIRO_FULL, "compreensao": ps.ROTEIRO_COMPREENSAO}[args.roteiro]
    audios = await asyncio.to_thread(ps.sintetiza, {k: ps.FALAS[k] for k in set(roteiro)}, Path(tempfile.gettempdir()) / "chamada_teste" / "tts")

    twirp("RoomService", "CreateRoom", {"name": sala, "empty_timeout": 30, "departure_timeout": 5}, sala)
    twirp("AgentDispatchService", "CreateDispatch", {"room": sala, "agent_name": ENV.get("AGENT_NAME", "rapia-voice"),
                                                     "metadata": json.dumps({"agent_id": args.agent_id})}, sala)

    sessao = ps.Sessao()
    room = rtc.Room()

    @room.on("track_subscribed")
    def _sub(track, _pub, part) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO and part.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            asyncio.create_task(ps.consome_audio_do_agente(sessao, track))

    token = jwt({"sub": "teste_paciente", "name": "Paciente de teste",
                 "video": {"room": sala, "roomJoin": True, "canPublish": True, "canSubscribe": True}}, ttl=3600)
    await room.connect(ENV["LIVEKIT_URL"], token)
    sessao.t0 = time.monotonic()
    fonte = rtc.AudioSource(ps.SAMPLE_RATE_CLIENTE, 1)
    trilha = rtc.LocalAudioTrack.create_audio_track("microfone-teste", fonte)
    await room.local_participant.publish_track(trilha, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))

    def agente_presente() -> bool:
        return any(p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT for p in room.remote_participants.values())

    if not await ps.espera(agente_presente, 30):
        print("FAIL: agente não entrou em 30 s", flush=True)
        await room.disconnect()
        twirp("RoomService", "DeleteRoom", {"room": sala}, sala)
        return 1
    print(f"agente entrou ({sessao.agora():.1f}s)", flush=True)

    async def conversa() -> None:
        # espera a saudação (áudio do agente) e fala cada passo quando ele cala
        await ps.espera(lambda: sessao.primeiro_ativo is not None, 45)
        for passo in roteiro:
            await ps.espera(lambda: sessao.primeiro_ativo is not None and sessao.agora() - sessao.ultimo_ativo > 1.5, 45)
            print(f"-> paciente: {ps.FALAS[passo]}", flush=True)
            antes = sessao.ultimo_ativo
            await ps.fala(fonte, audios[passo])
            await ps.espera(lambda: sessao.ultimo_ativo > antes + 0.5, 30)
        await ps.espera(lambda: sessao.agora() - sessao.ultimo_ativo > 1.5, 45)

    if args.cortar_apos:
        # ligação que cai no meio: corta aos N s, esteja quem estiver falando
        try:
            await asyncio.wait_for(conversa(), timeout=args.cortar_apos)
        except asyncio.TimeoutError:
            falando = sessao.agora() - sessao.ultimo_ativo < 0.3
            print(f"cortando aos {args.cortar_apos}s (agente falando: {falando})", flush=True)
        args.cortar = True
    else:
        await conversa()

    # paciente continua falando depois do roteiro (ex.: esperando na fila)
    for _ in range(args.insistir):
        await asyncio.sleep(4)
        print("-> paciente (insistindo): Sim, está correto.", flush=True)
        await ps.fala(fonte, audios["sim"])

    if args.segurar:
        print(f"segurando a ligação por {args.segurar}s...", flush=True)
        await asyncio.sleep(args.segurar)

    print("estado antes de sair:", json.dumps(estado_no_rapia(sala), ensure_ascii=False), flush=True)
    await room.disconnect()
    if args.cortar:
        # simula "ligação caiu": apaga a sala sem esperar o agente fechar
        twirp("RoomService", "DeleteRoom", {"room": sala}, sala)
    else:
        await asyncio.sleep(3)
        try:
            twirp("RoomService", "DeleteRoom", {"room": sala}, sala)
        except Exception:
            pass  # o agente já fechou a sala
    await asyncio.sleep(args.espera_fim)
    print("estado depois do fim:", json.dumps(estado_no_rapia(sala), ensure_ascii=False), flush=True)
    return 0


def principal() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roteiro", choices=["quick", "full", "compreensao"], default="full")
    ap.add_argument("--numero", default="84999000001", help="número no nome da sala (faixa fictícia 849990000NN)")
    ap.add_argument("--agent-id", type=int, default=1)
    ap.add_argument("--segurar", type=int, default=0, help="segundos com a ligação aberta depois do roteiro")
    ap.add_argument("--cortar", action="store_true", help="apaga a sala direto (ligação que cai)")
    ap.add_argument("--insistir", type=int, default=0, help="depois do roteiro, o paciente fala mais N vezes (roteiro full)")
    ap.add_argument("--cortar-apos", type=float, default=0, help="corta a ligação (DeleteRoom) N s depois do agente entrar, no meio da conversa")
    ap.add_argument("--espera-fim", type=int, default=25, help="segundos esperando o pós-chamada antes de ler o estado final")
    ap.add_argument("--remover", metavar="SALA", help="apaga do banco uma chamada de teste (só call-api_849990000*)")
    args = ap.parse_args()
    if args.remover:
        remover(args.remover)
        return 0
    return asyncio.run(executa(args))


if __name__ == "__main__":
    sys.exit(principal())
