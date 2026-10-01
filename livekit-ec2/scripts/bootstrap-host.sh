#!/usr/bin/env bash
# Prepara a EC2 (Ubuntu 22.04/24.04 ou Amazon Linux 2023) para rodar a stack:
#   - Docker Engine + plugin compose
#   - gettext (envsubst) e openssl
#   - ajustes de kernel para mídia UDP
# Uso: sudo ./scripts/bootstrap-host.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Rode com sudo." >&2; exit 1; fi

. /etc/os-release
echo "Sistema: $PRETTY_NAME"

case "$ID" in
  ubuntu|debian)
    apt-get update -y
    apt-get install -y ca-certificates curl gettext-base openssl
    if ! command -v docker >/dev/null; then
      curl -fsSL https://get.docker.com | sh
    fi
    ;;
  amzn)
    dnf install -y docker gettext openssl
    if ! docker compose version >/dev/null 2>&1; then
      mkdir -p /usr/local/lib/docker/cli-plugins
      curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
      chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    fi
    ;;
  *)
    echo "Distribuição $ID não prevista; instale Docker + compose + gettext manualmente." >&2; exit 1;;
esac

systemctl enable --now docker

# Usuário padrão da AMI no grupo docker (ubuntu / ec2-user)
for u in ubuntu ec2-user; do id "$u" >/dev/null 2>&1 && usermod -aG docker "$u" || true; done

# Buffers UDP maiores: reduz perda de pacotes de áudio sob carga
cat > /etc/sysctl.d/99-livekit.conf <<'EOF'
net.core.rmem_max = 5000000
net.core.wmem_max = 5000000
net.core.rmem_default = 1000000
net.core.wmem_default = 1000000
net.ipv4.udp_rmem_min = 16384
net.ipv4.udp_wmem_min = 16384
EOF
sysctl --system >/dev/null

echo
echo "Pronto. Saia e entre de novo na sessão SSH para usar docker sem sudo."
docker --version
docker compose version
