#!/usr/bin/env bash
# Cria no LiveKit desta EC2 os trunks e dispatch rules equivalentes aos do
# ambiente local (criados lá pelo voice-agent/scripts/dispatch.py):
#   ia           +558431901994 -> sala call-api_*       + agente rapia-voice (agent_id 1)
#   fila-direta  9990101       -> sala fila-api_*       (URA opção 2, sem IA)
#   fila-padrao  9990102       -> sala filapadrao-api_* (URA timeout, sem IA)
#   ramais       catch-all     -> sala ext-api_*        (sem IA)
#   + trunk de saída para 127.0.0.1:5060 (Asterisk), caller ID = DID
#
# Uso:  ./scripts/provisiona-sip.sh            # cria (recusa se já houver trunks)
#       ./scripts/provisiona-sip.sh listar
# Precisa do CLI "lk" (curl -sSL https://get.livekit.io/cli | bash).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; source .env; set +a
export LIVEKIT_URL=http://127.0.0.1:7880

listar() { lk sip inbound list; lk sip outbound list; lk sip dispatch list; }

if [[ "${1:-}" == "listar" ]]; then listar; exit 0; fi

if lk sip inbound list --json | grep -q '"sipTrunkId"'; then
  echo "Já existem trunks de entrada neste LiveKit. Nada criado (use 'listar')." >&2
  exit 1
fi

for k in ia fila-direta fila-padrao ramais; do
  tid=$(lk sip inbound create "sip/inbound-$k.json" | grep -oE 'ST_[A-Za-z0-9]+' | head -1)
  [[ -n "$tid" ]] || { echo "ERRO ao criar trunk $k" >&2; exit 1; }
  tmp=$(mktemp)
  sed "s/__TRUNK_ID__/$tid/" "sip/dispatch-$k.json" > "$tmp"
  rid=$(lk sip dispatch create "$tmp" | grep -oE 'SDR_[A-Za-z0-9]+' | head -1)
  rm -f "$tmp"
  [[ -n "$rid" ]] || { echo "ERRO ao criar dispatch rule $k" >&2; exit 1; }
  echo "  $k: trunk $tid  regra $rid"
done

oid=$(lk sip outbound create sip/outbound-trunk.json | grep -oE 'ST_[A-Za-z0-9]+' | head -1)
echo "  saida: trunk $oid"
echo
listar
