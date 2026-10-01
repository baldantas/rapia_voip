#!/usr/bin/env bash
# Gera config/*.conf a partir de templates/*.tmpl usando o .env.
# Só as variáveis listadas abaixo são substituídas: ${EXTEN}, ${CALLERID(num)}
# etc. do dialplan ficam intactas.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Falta o .env: cp .env.example .env e preencha"; exit 1; }
set -a; . ./.env; set +a

faltando=()
for v in PUBLIC_IP VPC_CIDR SIP_PROVIDER_HOST SIP_PROVIDER_PORT SIP_USERNAME SIP_AUTH_USERNAME SIP_PASSWORD SIP_REG_EXPIRY; do
  [ -n "${!v:-}" ] || faltando+=("$v")
done
[ ${#faltando[@]} -eq 0 ] || { echo "Variáveis vazias no .env: ${faltando[*]}"; exit 1; }

command -v envsubst >/dev/null || { echo "Instale o envsubst: sudo apt-get install -y gettext-base"; exit 1; }

vars='$PUBLIC_IP $VPC_CIDR $SIP_PROVIDER_HOST $SIP_PROVIDER_PORT $SIP_USERNAME $SIP_AUTH_USERNAME $SIP_PASSWORD $SIP_REG_EXPIRY'
mkdir -p config
for t in templates/*.tmpl; do
  out="config/$(basename "$t" .tmpl)"
  envsubst "$vars" < "$t" > "$out"
  echo "  -> $out"
done
# pjsip.conf tem a senha SIP. Não dá pra usar 600 (o Asterisk dentro do
# container roda com outro usuário e precisa ler o arquivo montado); quem
# protege é a pasta: chmod 700 nela (ver README).
chmod 700 .
echo "Configs geradas. Suba com: docker compose up -d"
