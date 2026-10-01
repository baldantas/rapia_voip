"""Alterna a dispatch rule do LiveKit entre o modo de teste e o modo agente de IA.

  modo "teste"  -> toda chamada cai na sala fixa "teste-sip" (ninguém atende;
                   você entra pelo softphone de teste)
  modo "agente" -> uma sala "call-*" por chamada + despacho do agente de IA

Uso (com o venv do voice-agent):
  .venv\\Scripts\\python.exe scripts\\dispatch.py listar
  .venv\\Scripts\\python.exe scripts\\dispatch.py agente
  .venv\\Scripts\\python.exe scripts\\dispatch.py teste
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ENV_LIVEKIT = BASE.parent / "livekit-local" / ".env"
ENV_AGENTE = BASE / ".env"
API = "http://localhost:7880/twirp/livekit.SIP/"


def le_env(caminho: Path) -> dict[str, str]:
    if not caminho.exists():
        return {}
    dados = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            chave, valor = linha.split("=", 1)
            dados[chave.strip()] = valor.strip()
    return dados


env = le_env(ENV_LIVEKIT)
env_agente = le_env(ENV_AGENTE)
KEY = env.get("LIVEKIT_API_KEY", "")
SECRET = env.get("LIVEKIT_API_SECRET", "")
DID = env.get("SIP_DID", "")
AGENT_NAME = env_agente.get("AGENT_NAME", "rapia-voice")
# Tenant embutido no nome da sala (call-{tenant}_{numero}_{aleatorio}). Local: "api".
# O subdomínio de tenant tem só letras e números, então "_" nunca aparece nele.
TENANT = env_agente.get("TENANT", "api")
# M1: agente de voz (voice_agents.id no RAPIA) despachado para cada chamada.
# Vai em room_config.agents[0].metadata (RoomAgentDispatch.metadata, confirmado
# no protobuf livekit.protocol.room) e chega ao worker em ctx.job.metadata —
# ver agent.py::agent_id_do_job.
AGENT_ID = env_agente.get("VOICE_AGENT_ID", "1")

if not KEY or not SECRET:
    sys.exit(f"Não encontrei LIVEKIT_API_KEY/SECRET em {ENV_LIVEKIT}")


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def token() -> str:
    agora = int(time.time())
    payload = {"iss": KEY, "sub": "dispatch-cli", "nbf": agora - 10, "exp": agora + 300,
               "sip": {"admin": True}}
    cabecalho = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    corpo = _b64(json.dumps(payload).encode())
    assinatura = hmac.new(SECRET.encode(), f"{cabecalho}.{corpo}".encode(), hashlib.sha256).digest()
    return f"{cabecalho}.{corpo}.{_b64(assinatura)}"


def api(metodo: str, corpo: dict) -> dict:
    req = urllib.request.Request(
        API + metodo,
        data=json.dumps(corpo).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=10))
    except urllib.error.HTTPError as erro:
        sys.exit(f"Erro {erro.code} em {metodo}: {erro.read().decode()}")
    except urllib.error.URLError as erro:
        sys.exit(f"LiveKit não respondeu em {API} ({erro.reason}). A stack está de pé?")


def trunk_id() -> str:
    trunks = api("ListSIPInboundTrunk", {}).get("items", [])
    if not trunks:
        # acontece depois de um "docker compose down" feito com o Redis ainda efêmero
        modelo = ENV_LIVEKIT.parent / "sip" / "inbound-trunk.json"
        if not modelo.exists():
            sys.exit(f"Nenhum trunk de entrada no LiveKit e {modelo} não existe.")
        criado = api("CreateSIPInboundTrunk", json.loads(modelo.read_text(encoding="utf-8")))
        print(f"  trunk recriado a partir de {modelo.name}: {criado['sip_trunk_id']}")
        return criado["sip_trunk_id"]
    for trunk in trunks:
        if DID and DID in trunk.get("numbers", []):
            return trunk["sip_trunk_id"]
    return trunks[0]["sip_trunk_id"]


def limpa_regras(tid: str) -> None:
    for regra in api("ListSIPDispatchRule", {}).get("items", []):
        if not regra.get("trunk_ids") or tid in regra.get("trunk_ids", []):
            api("DeleteSIPDispatchRule", {"sip_dispatch_rule_id": regra["sip_dispatch_rule_id"]})
            print(f"  removida: {regra['sip_dispatch_rule_id']} ({regra.get('name', '')})")


# M2.5: números fictícios da URA (opção 2 = fila direta, timeout = fila
# padrão) - mesmos valores do [globals] em extensions.conf.tmpl. Nunca são
# discados de fora; só existem pra fazer o LiveKit escolher um trunk sem
# agente. Ver o comentário em extensions.conf.tmpl para o raciocínio completo.
TRUNKS_URA = [
    ("9990101", "URA - fila direta (opção 2, sem IA)", "fila-" + TENANT),
    ("9990102", "URA - fila padrão (timeout, sem IA)", "filapadrao-" + TENANT),
]


NOME_TRUNK_RAMAIS = "Ramais internos - sala pessoal (catch-all)"
NOME_REGRA_RAMAIS = "Ramais internos - sala pessoal (catch-all)"
ROOM_PREFIX_RAMAIS = "ext-" + TENANT


def garante_trunk_ramais() -> None:
    """Trunk único e catch-all (sem 'numbers', só allowed_addresses) pra
    TODAS as ligações de ramal->ramal: o Asterisk disca PJSIP/{ramal-alvo}@
    livekit e o LiveKit aceita qualquer número discado por esse IP. O ramal
    discado chega ao webhook como atributo sip.trunkPhoneNumber do
    participante (não dá pra usar o nome da sala pra isso - ver comentário em
    extensions.conf.tmpl, contexto [ramais])."""
    trunks_existentes = {t.get("name"): t for t in api("ListSIPInboundTrunk", {}).get("items", [])}
    regras_existentes = {r.get("name") for r in api("ListSIPDispatchRule", {}).get("items", [])}

    trunk = trunks_existentes.get(NOME_TRUNK_RAMAIS)
    if trunk:
        tid = trunk["sip_trunk_id"]
    else:
        criado = api("CreateSIPInboundTrunk", {
            "trunk": {"name": NOME_TRUNK_RAMAIS, "allowed_addresses": ["172.30.0.10/32"]},
        })
        tid = criado["sip_trunk_id"]
        print(f"  trunk de ramais criado: {tid}")

    if NOME_REGRA_RAMAIS not in regras_existentes:
        api("CreateSIPDispatchRule", {
            "dispatch_rule": {
                "name": NOME_REGRA_RAMAIS,
                "trunk_ids": [tid],
                "rule": {"dispatchRuleIndividual": {"roomPrefix": ROOM_PREFIX_RAMAIS}},
                # de propósito: sem room_config.agents -> sala nasce sem IA
            },
        })
        print(f"  dispatch rule de ramais criada: {NOME_REGRA_RAMAIS}")


def garante_trunks_ura() -> None:
    """Cria (se não existir) o trunk + dispatch rule de cada destino "sem
    agente" da URA. Idempotente: roda toda vez que dispatch.py é chamado
    (iniciar.ps1 chama a cada subida) sem duplicar nada."""
    trunks_existentes = {t.get("name"): t for t in api("ListSIPInboundTrunk", {}).get("items", [])}
    regras_existentes = {r.get("name") for r in api("ListSIPDispatchRule", {}).get("items", [])}

    for numero, nome_trunk, room_prefix in TRUNKS_URA:
        trunk = trunks_existentes.get(nome_trunk)
        if trunk:
            tid = trunk["sip_trunk_id"]
        else:
            criado = api("CreateSIPInboundTrunk", {
                "trunk": {"name": nome_trunk, "numbers": [numero], "allowed_addresses": ["172.30.0.10/32"]},
            })
            tid = criado["sip_trunk_id"]
            print(f"  trunk da URA criado: {tid} ({nome_trunk})")

        nome_regra = nome_trunk.replace("URA - ", "URA - sala: ")
        if nome_regra not in regras_existentes:
            api("CreateSIPDispatchRule", {
                "dispatch_rule": {
                    "name": nome_regra,
                    "trunk_ids": [tid],
                    "rule": {"dispatchRuleIndividual": {"roomPrefix": room_prefix}},
                    # de propósito: sem room_config.agents -> sala nasce sem IA
                },
            })
            print(f"  dispatch rule da URA criada: {nome_regra}")


def listar() -> None:
    print("Trunks de entrada:")
    for trunk in api("ListSIPInboundTrunk", {}).get("items", []):
        print(f"  {trunk['sip_trunk_id']}  {trunk.get('numbers')}  origem={trunk.get('allowed_addresses')}")
    print("Dispatch rules:")
    for regra in api("ListSIPDispatchRule", {}).get("items", []):
        agentes = [a.get("agent_name") for a in (regra.get("room_config") or {}).get("agents", [])]
        print(f"  {regra['sip_dispatch_rule_id']}  {regra.get('name')}  trunks={regra.get('trunk_ids')}"
              f"  regra={regra.get('rule')}  agentes={agentes or '-'}")


def aplica(modo: str) -> None:
    tid = trunk_id()
    print(f"Trunk: {tid}")
    limpa_regras(tid)

    if modo == "teste":
        regra = {
            "name": "Teste - sala fixa teste-sip",
            "trunk_ids": [tid],
            "rule": {"dispatchRuleDirect": {"roomName": "teste-sip"}},
        }
    else:
        regra = {
            "name": "Agente de IA - uma sala por chamada",
            "trunk_ids": [tid],
            "rule": {"dispatchRuleIndividual": {"roomPrefix": f"call-{TENANT}"}},
            "room_config": {"agents": [{"agent_name": AGENT_NAME, "metadata": json.dumps({"agent_id": int(AGENT_ID)})}]},
        }

    criada = api("CreateSIPDispatchRule", {"dispatch_rule": regra})
    print(f"  criada: {criada['sip_dispatch_rule_id']}  ({regra['name']})")
    if modo == "agente":
        print(f"  agente despachado: {AGENT_NAME} (o worker precisa estar rodando)")


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "listar"
    if acao == "listar":
        listar()
    elif acao in ("teste", "agente"):
        aplica(acao)
        garante_trunks_ura()
        garante_trunk_ramais()
        print()
        listar()
    else:
        sys.exit("Use: listar | teste | agente")
