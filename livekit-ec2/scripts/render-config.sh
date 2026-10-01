#!/usr/bin/env bash
# Gera ./config/* a partir de ./templates/*.tmpl usando as variáveis do .env
#
# Uso:
#   ./scripts/render-config.sh              # renderiza as configs
#   ./scripts/render-config.sh --gen-keys   # preenche no .env as chaves vazias
#                                           # (LIVEKIT_API_KEY/SECRET, REDIS_PASSWORD, AMI_SECRET)
# Depois de mudar o .env com a stack no ar:
#   docker compose restart livekit sip                        (livekit.yaml / sip.yaml)
#   docker compose exec asterisk asterisk -rx 'dialplan reload'  (extensions.conf, ex.: URA_ATIVA)
#   docker compose exec asterisk asterisk -rx 'pjsip reload'     (pjsip.conf)
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=.env

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERRO: $ENV_FILE não encontrado. Rode: cp .env.example .env" >&2
  exit 1
fi

command -v envsubst >/dev/null || { echo "ERRO: envsubst ausente (instale gettext-base / gettext)" >&2; exit 1; }
command -v openssl  >/dev/null || { echo "ERRO: openssl ausente" >&2; exit 1; }

sed -i 's/\r$//' "$ENV_FILE"   # .env editado no Windows

set_env() { # set_env CHAVE VALOR  -> grava no .env somente se estiver vazia
  local key="$1" val="$2"
  if grep -qE "^${key}=$" "$ENV_FILE"; then
    sed -i "s|^${key}=$|${key}=${val}|" "$ENV_FILE"
    echo "  ${key} gerado"
  fi
}

if [[ "${1:-}" == "--gen-keys" ]]; then
  echo "Gerando segredos vazios no $ENV_FILE ..."
  set_env LIVEKIT_API_KEY "API$(openssl rand -hex 6)"
  set_env LIVEKIT_API_SECRET "$(openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-48)"
  set_env REDIS_PASSWORD "$(openssl rand -hex 24)"
  set_env AMI_SECRET "$(openssl rand -hex 24)"
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${SIP_AUTH_USERNAME:=${SIP_USERNAME:-}}"   # cai para o usuário da conta
# o painel do provedor costuma mostrar "numero@dominio", mas o PJSIP quer só a
# parte do usuário (o domínio vem de SIP_PROVIDER_HOST)
for v in SIP_USERNAME SIP_AUTH_USERNAME; do
  case "${!v:-}" in
    *@*) printf '  aviso: %s tinha domínio junto; usando apenas "%s"\n' "$v" "${!v%%@*}"
         printf -v "$v" '%s' "${!v%%@*}" ;;
  esac
done
export SIP_USERNAME SIP_AUTH_USERNAME
export SIP_OUT_PREFIX="${SIP_OUT_PREFIX:-}"   # pode ser vazio de propósito
export URA_ATIVA="${URA_ATIVA:-0}"            # URA pausada por padrão (M2.5)
export RAPIA_BASE_URL="${RAPIA_BASE_URL%/}"

# ---- validações -------------------------------------------------------------
fail=0
ipv4='^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
if [[ -n "${SIP_DID:-}" && ! "$SIP_DID" =~ ^\+[0-9]{8,15}$ ]]; then
  echo "ERRO: SIP_DID deve estar em E.164, ex.: +558431901994 (atual: $SIP_DID)" >&2; fail=1
fi
for v in PUBLIC_IP NODE_IP VPC_CIDR LIVEKIT_API_KEY LIVEKIT_API_SECRET REDIS_PASSWORD \
         RAPIA_BASE_URL URA_API_TOKEN URA_CURL_CONNTIMEOUT URA_CURL_HTTPTIMEOUT \
         SIP_PROVIDER_HOST SIP_PROVIDER_PORT SIP_USERNAME SIP_AUTH_USERNAME SIP_PASSWORD \
         SIP_REG_EXPIRY SIP_DID SIP_PORT AST_RTP_START AST_RTP_END \
         LIVEKIT_SIP_PORT SIP_RTP_START SIP_RTP_END SIP_MAX_ACTIVE_CALLS \
         AMI_PORT AMI_USER AMI_SECRET LOG_LEVEL; do
  if [[ -z "${!v:-}" ]]; then
    echo "ERRO: variável $v vazia no .env" >&2; fail=1
  fi
done
for v in PUBLIC_IP NODE_IP; do
  if [[ -n "${!v:-}" && ! "${!v}" =~ $ipv4 ]]; then echo "ERRO: $v inválido: ${!v}" >&2; fail=1; fi
done
if [[ ${#LIVEKIT_API_SECRET} -lt 32 ]]; then
  echo "ERRO: LIVEKIT_API_SECRET precisa ter 32+ caracteres" >&2; fail=1
fi
for ip in ${SIP_PROVIDER_IN_IPS:-}; do
  [[ "$ip" =~ $ipv4 ]] || { echo "ERRO: IP inválido em SIP_PROVIDER_IN_IPS: $ip" >&2; fail=1; }
done
[[ $fail -eq 0 ]] || exit 1

# ---- blocos gerados ---------------------------------------------------------
if [[ -n "${LIVEKIT_WEBHOOK_URL:-}" ]]; then
  WEBHOOK_BLOCK=$(printf 'webhook:\n  api_key: %s\n  urls:\n    - %s' "$LIVEKIT_API_KEY" "$LIVEKIT_WEBHOOK_URL")
else
  WEBHOOK_BLOCK="# webhook desabilitado (LIVEKIT_WEBHOOK_URL vazio)"
fi
PROVIDER_MATCH_LINES=""
for ip in ${SIP_PROVIDER_IN_IPS:-}; do PROVIDER_MATCH_LINES+="match=${ip}"$'\n'; done
PROVIDER_MATCH_LINES="${PROVIDER_MATCH_LINES%$'\n'}"
export WEBHOOK_BLOCK PROVIDER_MATCH_LINES

# Apenas estas variáveis são substituídas (${EXTEN}, ${DID}, ${CALLERID(num)}...
# do dialplan ficam intactas para o Asterisk)
VARS='${PUBLIC_IP} ${NODE_IP} ${VPC_CIDR}
${LIVEKIT_API_KEY} ${LIVEKIT_API_SECRET} ${REDIS_PASSWORD} ${WEBHOOK_BLOCK} ${LOG_LEVEL}
${RAPIA_BASE_URL} ${URA_API_TOKEN} ${URA_CURL_CONNTIMEOUT} ${URA_CURL_HTTPTIMEOUT} ${URA_ATIVA}
${SIP_PROVIDER_HOST} ${SIP_PROVIDER_PORT} ${PROVIDER_MATCH_LINES} ${SIP_USERNAME} ${SIP_AUTH_USERNAME}
${SIP_PASSWORD} ${SIP_REG_EXPIRY} ${SIP_DID} ${SIP_OUT_PREFIX} ${SIP_PORT} ${AST_RTP_START} ${AST_RTP_END}
${LIVEKIT_SIP_PORT} ${SIP_RTP_START} ${SIP_RTP_END} ${SIP_MAX_ACTIVE_CALLS}
${AMI_PORT} ${AMI_USER} ${AMI_SECRET}'

mkdir -p config/asterisk data/redis
umask 077
# templates/*.tmpl -> config/*   e   templates/asterisk/*.tmpl -> config/asterisk/*
for tmpl in templates/*.tmpl templates/asterisk/*.tmpl; do
  [ -e "$tmpl" ] || continue
  rel="${tmpl#templates/}"
  out="config/${rel%.tmpl}"
  envsubst "$VARS" < "$tmpl" > "$out"
  echo "  -> $out"
done
# gravação (M5): só com S3_BUCKET; o serviço egress sobe pelo perfil "gravacao"
if [[ -n "${S3_BUCKET:-}" ]]; then
  for v in S3_REGION S3_ACCESS_KEY S3_SECRET; do
    [[ -n "${!v:-}" ]] || { echo "ERRO: S3_BUCKET preenchido, mas $v vazia no .env" >&2; exit 1; }
  done
  export S3_BUCKET S3_REGION S3_ACCESS_KEY S3_SECRET EGRESS_LOG_LEVEL="${EGRESS_LOG_LEVEL:-info}"
  envsubst '${LIVEKIT_API_KEY} ${LIVEKIT_API_SECRET} ${REDIS_PASSWORD} ${S3_BUCKET} ${S3_REGION} ${S3_ACCESS_KEY} ${S3_SECRET} ${EGRESS_LOG_LEVEL}' \
    < extras/egress.yaml.tmpl > config/egress.yaml
  echo "  -> config/egress.yaml (gravação)"
  [[ "${COMPOSE_PROFILES:-}" == *gravacao* ]] || echo "  aviso: COMPOSE_PROFILES sem 'gravacao': o egress não sobe no 'docker compose up -d'"
fi
# ramais: gerado pelo Laravel no ambiente local; aqui só garante o #include
[ -e config/asterisk/pjsip_ramais.conf ] || \
  echo '; ramais: vazio na EC2 de homologação (ver README)' > config/asterisk/pjsip_ramais.conf
chmod 644 config/*.* config/asterisk/*   # containers leem como usuário não-root

# ---- conferência: nenhuma variável do .env pode sobrar sem resolver ----------
sobras=$(grep -ohE '\$\{[A-Z_]+\}' config/*.yaml config/*.conf 2>/dev/null | sort -u || true)
if [[ -n "$sobras" ]]; then echo "ERRO: sobrou sem resolver em config/*: $sobras" >&2; exit 1; fi
for v in $(echo "$VARS" | grep -oE '[A-Z_]+'); do
  [[ "$v" == WEBHOOK_BLOCK || "$v" == PROVIDER_MATCH_LINES ]] && continue
  if grep -q "\${$v}" config/asterisk/*.conf; then echo "ERRO: \${$v} sobrou em config/asterisk" >&2; exit 1; fi
done

echo "Configs geradas. Suba com: docker compose up -d"
