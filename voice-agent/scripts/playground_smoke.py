"""Smoke test headless do Playground do Estúdio do Agente (M3, prova de risco).

Faz o papel do navegador: abre uma sessão do Playground, entra na sala pg-*,
FALA com o agente (TTS local do Windows, voz pt-BR) e prova, elo a elo:

  1. sessão criada (sala + versão pedida)
  2. agente despachado e presente na sala
  3. áudio agente -> cliente (grava o WAV e mede energia)
  4. áudio cliente -> agente (a fala chega como transcrição `patient` no RAPIA)
  5. transcrição `ai` chega ao RAPIA (e a marca do rascunho aparece, se pedida)
  6. eventos de tool chegam ao RAPIA (modo full); modo erp: o modelo chama a tool
     HTTP buscar_paciente (ERP Demo) e FALA o que o ERP devolveu
  7. sala pg-* não cria voice_calls (modo local)
  8. o agente sai da sala depois que o cliente sai

Como a sessão e o buffer são obtidos:
  - com --user-token (ou env RAPIA_USER_TOKEN, o users.token de um SUPER): HTTP
    real em POST /voice/playground/session e /voice/playground/events;
  - sem token (modo local): `php artisan tinker` em processo, como o usuário
    --user-id (padrão 9), chamando os mesmos controllers/serviço.

Uso (na pasta voice-agent):
  .venv\\Scripts\\python.exe scripts\\playground_smoke.py --mode quick --runs 3
  .venv\\Scripts\\python.exe scripts\\playground_smoke.py --mode full --marker abacaxi
  .venv\\Scripts\\python.exe scripts\\playground_smoke.py --version published --marker abacaxi --expect-marker no

Sai com código 0 se todos os checks passaram, 1 caso contrário.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

import numpy as np
from livekit import rtc

BASE = Path(__file__).resolve().parent.parent
SYSAPI = BASE.parent.parent / "sysapi"
PHP = os.getenv("PHP_BIN", r"C:\wamp64\bin\php\php7.4.33\php.exe")
API = os.getenv("RAPIA_API_URL", "http://api.ipsys/api").rstrip("/")
SAMPLE_RATE_CLIENTE = 16000
LIMIAR_RMS = 300  # int16; abaixo disso é ruído/silêncio

# Falas do cliente. Cada uma só é dita depois que o agente termina o turno
# anterior (nova transcrição `ai` no RAPIA + 1,2 s de silêncio de áudio).
FALAS = {
    "nome": "Meu nome é Maria da Silva Souza.",
    "sim": "Sim, está correto.",
    "cpf": "Meu CPF é cinco dois nove, nove oito dois, dois quatro sete, dois cinco.",
    "nascimento": "Nasci no dia primeiro de fevereiro de mil novecentos e noventa.",
    # M4.4: falas em espanhol para provocar comprehension_miss (modo compreensao)
    "es1": "Hola, buenos días. Necesito una cita con el médico, por favor.",
    "es2": "Me llamo Juana. ¿Usted me puede ayudar?",
    "es3": "No entiendo nada, ¿puede hablar más despacio?",
}
ROTEIRO_QUICK = ["nome"]
ROTEIRO_FULL = ["nome", "sim", "cpf", "sim", "nascimento", "sim"]
ROTEIRO_ERP = ["cpf"]  # agente de teste com a tool HTTP buscar_paciente (ERP Demo)
ROTEIRO_COMPREENSAO = ["es1", "es2", "es3"]  # M4.4: regra "não entendeu duas vezes" -> transferir

TENANT_PHP = (
    "$i = App\\Models\\SysConnect::where('subdominio','api')->first();"
    "config(['database.connections.tn'=>['driver'=>'mysql','host'=>$i->db_host ?? env('DB_APP_HOST'),"
    "'database'=>$i->db_instancia,'username'=>$i->db_usr ?? env('DB_APP_USER'),'password'=>$i->db_pwd ?? env('DB_APP_PWD'),"
    "'charset'=>'utf8mb4','collation'=>'utf8mb4_unicode_ci','prefix'=>'','strict'=>false]]);"
    "config(['database.default'=>'tn']);"
)


# ----------------------------------------------------------------- provisionamento
def tinker(snippet: str) -> Any:
    """Roda PHP no tenant `api` via tinker e devolve o JSON impresso entre marcadores."""
    codigo = TENANT_PHP + snippet
    proc = subprocess.run(
        [PHP, "artisan", "tinker", f"--execute={codigo}"],
        cwd=SYSAPI, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
    )
    saida = proc.stdout
    if "@@" not in saida:
        raise RuntimeError(f"tinker sem resultado: {saida[-400:]} {proc.stderr[-300:]}")
    return json.loads(saida.split("@@")[1])


def http(metodo: str, caminho: str, corpo: dict, token: str) -> Any:
    req = urllib.request.Request(
        f"{API}{caminho}", data=json.dumps(corpo).encode(), method=metodo,
        headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} em {caminho}: {e.read()[:300]!r}") from e


class Provedor:
    def __init__(self, user_token: str | None, user_id: int):
        self.user_token = user_token
        self.user_id = user_id

    @property
    def rotulo(self) -> str:
        return "HTTP (users.token)" if self.user_token else f"local (tinker, usuário {self.user_id})"

    def abre_sessao(self, agent_id: int, version: str) -> dict:
        if self.user_token:
            return http("POST", "/voice/playground/session", {"agent_id": agent_id, "version": version}, self.user_token)["data"]
        return tinker(
            f"$u = App\\Models\\User::find({self.user_id});"
            "$c = app(App\\Http\\Controllers\\Rapia\\Voice\\VoicePlaygroundController::class);"
            f"$r = Illuminate\\Http\\Request::create('/x','POST',['agent_id'=>{agent_id},'version'=>'{version}']);"
            "$r->setUserResolver(function() use ($u){return $u;});"
            "$o = json_decode($c->session($r)->getContent(),true);"
            "echo '@@'.json_encode($o['data'] ?? $o).'@@';"
        )

    def le_eventos(self, sala: str, depois: int) -> list[dict]:
        if self.user_token:
            return http("POST", "/voice/playground/events", {"room": sala, "after_id": depois}, self.user_token)["data"]["events"]
        return tinker(
            f"echo '@@'.json_encode(App\\Services\\Voice\\PlaygroundBuffer::le('{sala}', {depois})).'@@';"
        )

    def conta_chamadas(self) -> int | None:
        if self.user_token:
            return None
        return tinker("echo '@@'.json_encode(DB::table('voice_calls')->count()).'@@';")


# ----------------------------------------------------------------- áudio
def sintetiza(frases: dict[str, str], pasta: Path) -> dict[str, np.ndarray]:
    """Gera um WAV por fala com a voz pt-BR do Windows (System.Speech) e devolve int16 mono 16 kHz."""
    pasta.mkdir(parents=True, exist_ok=True)
    entrada = pasta / "falas.json"
    entrada.write_text(json.dumps(frases, ensure_ascii=False), encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.SelectVoice('Microsoft Maria Desktop');"
        "$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono);"
        f"$falas = Get-Content -Raw -Encoding UTF8 '{entrada}' | ConvertFrom-Json;"
        f"foreach ($p in $falas.PSObject.Properties) {{ $s.SetOutputToWaveFile('{pasta}\\' + $p.Name + '.wav', $fmt); $s.Speak($p.Value); $s.SetOutputToNull() }}"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=120)
    saida: dict[str, np.ndarray] = {}
    for nome in frases:
        caminho = pasta / f"{nome}.wav"
        if not caminho.exists():
            raise RuntimeError(f"TTS não gerou {caminho}: {proc.stderr[-300:]}")
        with wave.open(str(caminho), "rb") as w:
            assert w.getframerate() == SAMPLE_RATE_CLIENTE and w.getnchannels() == 1 and w.getsampwidth() == 2
            saida[nome] = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).copy()
    return saida


class Sessao:
    """Estado compartilhado de uma execução: eventos do RAPIA e atividade de áudio do agente."""

    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.eventos: list[dict] = []
        self.audio_agente: list[np.ndarray] = []
        self.audio_rate = 48000
        self.ativo_seg = 0.0
        self.pico_rms = 0.0
        self.ultimo_ativo = 0.0
        self.primeiro_ativo: float | None = None

    def agora(self) -> float:
        return time.monotonic() - self.t0

    def ai(self) -> list[dict]:
        return [e for e in self.eventos if e["type"] == "transcript" and e.get("role") == "ai"]

    def paciente(self) -> list[dict]:
        return [e for e in self.eventos if e["type"] == "transcript" and e.get("role") == "patient"]

    def maior_id(self) -> int:
        return max((e["id"] for e in self.eventos), default=0)


async def consome_audio_do_agente(sessao: Sessao, track: rtc.Track) -> None:
    async for ev in rtc.AudioStream(track):
        amostras = np.frombuffer(ev.frame.data, dtype=np.int16)
        sessao.audio_rate = ev.frame.sample_rate
        sessao.audio_agente.append(amostras.copy())
        rms = float(np.sqrt(np.mean(amostras.astype(np.float64) ** 2))) if amostras.size else 0.0
        sessao.pico_rms = max(sessao.pico_rms, rms)
        if rms > LIMIAR_RMS:
            sessao.ativo_seg += amostras.size / ev.frame.sample_rate
            sessao.ultimo_ativo = sessao.agora()
            if sessao.primeiro_ativo is None:
                sessao.primeiro_ativo = sessao.agora()


async def poller(sessao: Sessao, prov: Provedor, sala: str, parar: asyncio.Event) -> None:
    while not parar.is_set():
        try:
            novos = await asyncio.to_thread(prov.le_eventos, sala, sessao.maior_id())
            sessao.eventos.extend(novos)
        except Exception as exc:  # o teste segue; a falta de eventos vira FAIL nos checks
            print(f"   (aviso: leitura do buffer falhou: {exc})", flush=True)
        await asyncio.sleep(1.0)


async def espera(cond, timeout: float, passo: float = 0.4) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        await asyncio.sleep(passo)
    return False


class MicrofoneComRuido:
    """M4.4: microfone simulado que envia ruído branco contínuo (nível em dBFS)
    e mistura as falas por cima — para o worker medir SNR/ruído no Playground.
    Sem ele, o smoke só envia áudio enquanto fala (o resto chega como silêncio
    digital)."""

    def __init__(self, fonte: rtc.AudioSource, ruido_dbfs: float) -> None:
        self.fonte = fonte
        self.desvio = 32768 * 10 ** (ruido_dbfs / 20)
        self.pendente = np.zeros(0, dtype=np.int16)
        self.rng = np.random.default_rng(7)
        self.tarefa = asyncio.create_task(self._envia())

    async def _envia(self) -> None:
        bloco = SAMPLE_RATE_CLIENTE // 100
        while True:
            parte = self.rng.normal(0, self.desvio, bloco)
            if self.pendente.size:
                fala_ = self.pendente[:bloco].astype(np.float64)
                self.pendente = self.pendente[bloco:]
                parte[: fala_.size] += fala_
            frame = rtc.AudioFrame.create(SAMPLE_RATE_CLIENTE, 1, bloco)
            np.frombuffer(frame.data, dtype=np.int16)[:] = np.clip(parte, -32768, 32767).astype(np.int16)
            await self.fonte.capture_frame(frame)

    async def fala(self, amostras: np.ndarray) -> None:
        self.pendente = np.concatenate([self.pendente, amostras])
        while self.pendente.size:
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)

    async def para(self) -> None:
        self.tarefa.cancel()


async def fala(fonte: rtc.AudioSource, amostras: np.ndarray) -> None:
    preenchida = np.concatenate([np.zeros(SAMPLE_RATE_CLIENTE // 4, dtype=np.int16), amostras, np.zeros(SAMPLE_RATE_CLIENTE // 2, dtype=np.int16)])
    bloco = SAMPLE_RATE_CLIENTE // 100  # 10 ms
    for i in range(0, len(preenchida), bloco):
        parte = preenchida[i:i + bloco]
        if len(parte) < bloco:
            parte = np.pad(parte, (0, bloco - len(parte)))
        frame = rtc.AudioFrame.create(SAMPLE_RATE_CLIENTE, 1, bloco)
        np.frombuffer(frame.data, dtype=np.int16)[:] = parte
        await fonte.capture_frame(frame)
    await fonte.wait_for_playout()


# ----------------------------------------------------------------- execução
async def executa(args, prov: Provedor, audios: dict[str, np.ndarray], numero: int) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    def check(nome: str, ok: bool, detalhe: str) -> None:
        checks.append((nome, ok, detalhe))
        print(f"   [{'PASS' if ok else 'FAIL'}] {nome}: {detalhe}", flush=True)

    print(f"\n=== execução {numero} | modo={args.mode} versão={args.version} | provedor: {prov.rotulo}", flush=True)
    chamadas_antes = await asyncio.to_thread(prov.conta_chamadas)

    try:
        sess = await asyncio.to_thread(prov.abre_sessao, args.agent_id, args.version)
    except Exception as exc:
        check("1. sessão criada", False, str(exc))
        return checks
    check("1. sessão criada", "token" in sess, f"sala={sess.get('room')} versão={sess.get('version')}")
    if "token" not in sess:
        return checks

    sala = sess["room"]
    sessao = Sessao()
    parar = asyncio.Event()
    room = rtc.Room()

    @room.on("track_subscribed")
    def _sub(track: rtc.Track, pub: rtc.RemoteTrackPublication, part: rtc.RemoteParticipant) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO and part.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            asyncio.create_task(consome_audio_do_agente(sessao, track))

    await room.connect(sess["ws_url"], sess["token"])
    sessao.t0 = time.monotonic()
    fonte = rtc.AudioSource(SAMPLE_RATE_CLIENTE, 1)
    trilha = rtc.LocalAudioTrack.create_audio_track("microfone-teste", fonte)
    await room.local_participant.publish_track(trilha, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))
    task_poll = asyncio.create_task(poller(sessao, prov, sala, parar))
    mic = MicrofoneComRuido(fonte, args.ruido_dbfs) if args.ruido_dbfs is not None else None
    ganho = 10 ** (args.fala_ganho_db / 20)

    def agente_presente() -> bool:
        return any(p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT for p in room.remote_participants.values())

    entrou = await espera(agente_presente, 25)
    check("2. agente despachado e presente", entrou, f"{sessao.agora():.1f}s após entrar" if entrou else "não apareceu em 25s")
    if not entrou:
        for linha in diagnostico_despacho(sala):
            print(f"      livekit> {linha}", flush=True)
        parar.set(); await task_poll; await room.disconnect()
        return checks

    # saudação da IA
    saudou = await espera(lambda: len(sessao.ai()) >= 1, 45)
    check("5a. transcrição `ai` chegou ao RAPIA", saudou, f"saudação após {sessao.agora():.1f}s: {sessao.ai()[0]['text'][:70]!r}" if saudou else "sem fala da IA em 45s")

    roteiro = ROTEIRO_FULL if args.mode == "full" else ROTEIRO_ERP if args.mode == "erp" else ROTEIRO_COMPREENSAO if args.mode == "compreensao" else ROTEIRO_QUICK
    for passo in roteiro:
        if not saudou:
            break
        n_ai = len(sessao.ai())
        # só fala quando o agente calou (1,2 s sem áudio ativo)
        await espera(lambda: sessao.agora() - sessao.ultimo_ativo > 1.2, 30)
        print(f"   -> cliente diz ({passo}): {FALAS[passo]}", flush=True)
        amostras = audios[passo] if ganho == 1 else np.clip(audios[passo] * ganho, -32768, 32767).astype(np.int16)
        await (mic.fala(amostras) if mic else fala(fonte, amostras))
        respondeu = await espera(lambda: len(sessao.ai()) > n_ai, 45)
        if not respondeu:
            print(f"   (agente não respondeu ao passo {passo} em 45s)", flush=True)
            break
        print(f"   <- agente: {sessao.ai()[-1]['text'][:90]!r}", flush=True)

    if args.mode == "full":
        await espera(lambda: any(e["type"] == "tool_result" and e.get("name") == "transferir_para_atendente" for e in sessao.eventos), 45)
    await asyncio.sleep(2.5)  # deixa chegar o que ainda estiver em voo

    # --- avaliação
    dur_audio = sessao.ativo_seg
    check("3. áudio agente -> cliente", dur_audio > 1.0, f"{dur_audio:.1f}s de fala ativa, pico RMS {sessao.pico_rms:.0f}, 1º áudio em {sessao.primeiro_ativo and round(sessao.primeiro_ativo, 1)}s")
    pac = sessao.paciente()
    chave_fala = "5299" if args.mode == "erp" else "maria"
    ouviu = any(chave_fala in e["text"].lower().replace(".", "").replace("-", "").replace(" ", "") for e in pac)
    check("4. áudio cliente -> agente", ouviu, f"transcrições `patient` no RAPIA: {[e['text'][:60] for e in pac][:3]}")
    check("5b. transcrições no RAPIA", len(sessao.ai()) >= 1 and len(pac) >= 1, f"ai={len(sessao.ai())} patient={len(pac)}")

    if args.marker:
        primeira = sessao.ai()[0]["text"].lower() if sessao.ai() else ""
        tem = args.marker.lower() in primeira
        esperado = args.expect_marker == "yes"
        check(f"5c. marca {args.marker!r} {'presente' if esperado else 'ausente'} na 1ª fala", tem == esperado, f"1ª fala: {primeira[:80]!r}")

    if args.mode == "full":
        chamadas = [e for e in sessao.eventos if e["type"] == "tool_called"]
        resultados = [e for e in sessao.eventos if e["type"] == "tool_result"]
        triagem = [e for e in chamadas if e.get("name") == "registrar_triagem"]
        cpf_ok = bool(triagem) and "52998224725" in "".join(c for c in json.dumps(triagem[-1].get("arguments", {})) if c.isdigit())
        check("6a. tool registrar_triagem com os dados falados", cpf_ok, f"argumentos: {triagem[-1].get('arguments') if triagem else None}")
        res_tri = [e for e in resultados if e.get("name") == "registrar_triagem"]
        check("6b. resultado simulado devolvido", bool(res_tri) and all(e.get("simulated") for e in res_tri), f"{[e['result'].get('ok') for e in res_tri]}")
        check("6c. transferir_para_atendente", any(e.get("name") == "transferir_para_atendente" for e in chamadas), f"tools chamadas: {[e.get('name') for e in chamadas]}")

    if args.mode == "erp":
        chamadas = [e for e in sessao.eventos if e["type"] == "tool_called" and e.get("name") == "buscar_paciente"]
        resultados = [e for e in sessao.eventos if e["type"] == "tool_result" and e.get("name") == "buscar_paciente"]
        cpf_ok = bool(chamadas) and "52998224725" in "".join(c for c in json.dumps(chamadas[-1].get("arguments", {})) if c.isdigit())
        check("6a. modelo chamou buscar_paciente com o CPF falado", cpf_ok, f"argumentos: {chamadas[-1].get('arguments') if chamadas else None}")
        real = bool(resultados) and resultados[-1].get("simulated") is False and (resultados[-1].get("response") or {}).get("status") == 200
        check("6b. chamada HTTP REAL ao ERP Demo (200), segredo mascarado", real and "rapia-demo" not in json.dumps(resultados), f"status={(resultados[-1].get('response') or {}).get('status') if resultados else None} req={resultados[-1].get('request') if resultados else None}")
        dados = ((resultados[-1].get("result") or {}).get("data") or {}) if resultados else {}
        check("6c. modelo recebeu só os campos mapeados", set(dados) >= {"nome", "plano"}, f"{dados}")
        depois = [e["text"].lower() for e in sessao.ai()[1:]]
        check("6d. IA FALOU o que o ERP devolveu (nome/plano)", any(("maria" in t and ("coopab" in t or "essencial" in t)) for t in depois), f"falas: {[t[:80] for t in depois]}")

    # --- encerra e confere saída do agente
    audio_out = Path(args.out) / f"agente_{sala}.wav"
    audio_out.parent.mkdir(parents=True, exist_ok=True)
    if sessao.audio_agente:
        with wave.open(str(audio_out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sessao.audio_rate)
            w.writeframes(np.concatenate(sessao.audio_agente).tobytes())
        print(f"   áudio do agente salvo em {audio_out}", flush=True)

    if mic:
        await mic.para()
    await room.disconnect()
    # o agente deve fechar a sessão sozinho ao ver o cliente sair (close_on_disconnect)
    saiu = await asyncio.to_thread(sala_fechou, sala, 25)
    check("8. sala encerrada após o cliente sair", saiu, "sala fechou" if saiu else "sala ainda aberta em 25s")
    if args.expect_quality:
        # o resumo é publicado no encerramento do job: dá um tempo para chegar ao buffer
        await espera(lambda: any(e["type"] == "audio_quality_summary" for e in sessao.eventos), 20)
    parar.set(); await task_poll

    if args.expect_quality:
        janelas = [e.get("payload") or {} for e in sessao.eventos if e["type"] == "audio_quality"]
        resumo = next((e.get("payload") for e in sessao.eventos if e["type"] == "audio_quality_summary"), None)
        check("9a. audio_quality no buffer do Playground", len(janelas) >= 2,
              f"{len(janelas)} janelas: " + "; ".join(f"#{j.get('janela')} SNR {j.get('snr_db')} ruído {j.get('ruido_dbfs')} fala {j.get('fala_dbfs')} buracos {j.get('buracos_pct')}% silêncio {j.get('silencio_digital_pct')}%" for j in janelas))
        for e in (e for e in sessao.eventos if e["type"] == "comprehension_miss"):
            p = e.get("payload") or {}
            print(f"      comprehension_miss: {p.get('seguidas')} seguidas {p.get('motivos')} | paciente {p.get('texto_paciente')!r} | IA {str(p.get('texto_ia'))[:70]!r}", flush=True)
        check("9b. audio_quality_summary no fim", bool(resumo),
              json.dumps({k: resumo.get(k) for k in ("snr_mediana_db", "ruido_mediana_dbfs", "buracos_pct", "silencio_digital_pct", "gatilho_dispararia_na_janela", "cpu_processo_pct_nucleo", "cpu_medicao_ms", "incompreensoes", "incompreensoes_max_seguidas")}, ensure_ascii=False) if resumo else "não chegou")

    if chamadas_antes is not None:
        depois = await asyncio.to_thread(prov.conta_chamadas)
        check("7. sala pg-* não criou voice_calls", depois == chamadas_antes, f"antes={chamadas_antes} depois={depois}")
    return checks


def diagnostico_despacho(sala: str) -> list[str]:
    """Linhas do log do LiveKit sobre o despacho de agente desta sala (para achar a causa quando o agente não entra)."""
    try:
        proc = subprocess.run(["docker", "logs", "--since", "3m", "livekit-local-livekit-1"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=20)
        linhas = (proc.stdout + proc.stderr).splitlines()
    except Exception as exc:
        return [f"(não consegui ler o log do LiveKit: {exc})"]
    chaves = ("failed to send job", "assigned job", "no worker", "worker registered", "worker closed")
    return [l[:230] for l in linhas if any(k in l for k in chaves)][-6:]


def sala_fechou(sala: str, timeout: float) -> bool:
    import base64, hashlib, hmac
    env = {}
    # mesmo LiveKit e chaves do worker (local ou EC2 de homologação)
    for linha in (BASE / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            k, v = linha.split("=", 1)
            env[k.strip()] = v.strip()

    def b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    def token() -> str:
        agora = int(time.time())
        cab = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        cor = b64(json.dumps({"iss": env["LIVEKIT_API_KEY"], "sub": "smoke", "nbf": agora - 10, "exp": agora + 60,
                              "video": {"roomList": True}}).encode())
        sig = hmac.new(env["LIVEKIT_API_SECRET"].encode(), f"{cab}.{cor}".encode(), hashlib.sha256).digest()
        return f"{cab}.{cor}.{b64(sig)}"

    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        req = urllib.request.Request(
            env.get("LIVEKIT_URL", "ws://localhost:7880").replace("ws", "http", 1) + "/twirp/livekit.RoomService/ListRooms", data=b"{}",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            salas = [r["name"] for r in json.loads(resp.read()).get("rooms", [])]
        if sala not in salas:
            return True
        time.sleep(2)
    return False


async def principal() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["quick", "full", "erp", "compreensao"], default="quick", help="compreensao (M4.4): 3 falas em espanhol; quick: saudação + 1 fala; full: coleta completa com tools; erp: fala o CPF e espera a tool HTTP buscar_paciente")
    ap.add_argument("--runs", type=int, default=1, help="repete a execução N vezes (estabilidade do despacho)")
    ap.add_argument("--agent-id", type=int, default=1)
    ap.add_argument("--version", default="draft", help="draft | published | id da versão")
    ap.add_argument("--marker", default="", help="palavra que a 1ª fala da IA deve (ou não) conter")
    ap.add_argument("--expect-marker", choices=["yes", "no"], default="yes")
    ap.add_argument("--ruido-dbfs", type=float, default=None, help="M4.4: microfone envia ruído branco contínuo neste nível (ex.: -45) com as falas por cima")
    ap.add_argument("--fala-ganho-db", type=float, default=0.0, help="M4.4: ganho aplicado às falas do cliente (ex.: -20 = fala baixa)")
    ap.add_argument("--expect-quality", action="store_true", help="M4.4: exige eventos audio_quality/audio_quality_summary (agente com quality_guard != off)")
    ap.add_argument("--user-id", type=int, default=9, help="modo local: usuário SUPER usado pelo tinker")
    ap.add_argument("--user-token", default=os.getenv("RAPIA_USER_TOKEN"), help="users.token de um SUPER (modo HTTP)")
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "playground_smoke"), help="pasta dos WAVs gravados")
    args = ap.parse_args()

    prov = Provedor(args.user_token, args.user_id)
    pasta = Path(args.out) / "tts"
    roteiro = ROTEIRO_FULL if args.mode == "full" else ROTEIRO_ERP if args.mode == "erp" else ROTEIRO_COMPREENSAO if args.mode == "compreensao" else ROTEIRO_QUICK
    print(f"Gerando as falas do cliente (TTS local): {sorted(set(roteiro))}", flush=True)
    audios = await asyncio.to_thread(sintetiza, {k: FALAS[k] for k in set(roteiro)}, pasta)

    tudo: list[tuple[str, bool, str]] = []
    for n in range(1, args.runs + 1):
        tudo.extend(await executa(args, prov, audios, n))

    falhas = [c for c in tudo if not c[1]]
    print(f"\nRESULTADO: {len(tudo) - len(falhas)}/{len(tudo)} checks passaram em {args.runs} execução(ões)")
    for nome, _, detalhe in falhas:
        print(f"  FAIL {nome}: {detalhe}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(principal()))
