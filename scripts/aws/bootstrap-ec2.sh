#!/usr/bin/env bash
# Prepara una EC2 recién creada (Ubuntu 22.04 o 24.04) para correr BeeMatch.
# Se puede pegar en "Datos de usuario" al crear la instancia o ejecutar a mano:
#
#   curl -fsSL https://raw.githubusercontent.com/jalvarez01/BeeMatch/development/scripts/aws/bootstrap-ec2.sh | sudo bash
#   (si el repositorio es privado, copia el archivo con scp y ejecútalo con sudo)
#
# Es idempotente: se puede repetir sin daño.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta con sudo." >&2
  exit 1
fi

USUARIO="${SUDO_USER:-ubuntu}"
SWAP_GB="${SWAP_GB:-2}"

echo "==> Paquetes base"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git unattended-upgrades

echo "==> Docker (repositorio oficial)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$USUARIO" || true

echo "==> Memoria de intercambio (${SWAP_GB} GB): evita que el build o un pico maten procesos"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l "${SWAP_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Directorio de la aplicación"
install -d -o "$USUARIO" -g "$USUARIO" /opt/beematch /opt/beematch/respaldos

echo "==> Actualizaciones de seguridad automáticas"
dpkg-reconfigure -f noninteractive unattended-upgrades || true

echo
echo "Listo. Cierra la sesión y vuelve a entrar (para el grupo docker), luego:"
echo "  cd /opt/beematch && git clone <url-del-repositorio> app && cd app"
echo "  cp .env.production.example .env.production && chmod 600 .env.production && nano .env.production"
echo "  ./scripts/aws/desplegar.sh"
