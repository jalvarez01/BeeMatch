#!/usr/bin/env bash
# Restaura un respaldo. REEMPLAZA todo el contenido actual de la base.
#
#   ./scripts/aws/restaurar.sh respaldos/beematch-20261112-020000.dump
#
# Detiene la API y el worker mientras restaura y los vuelve a levantar.
source "$(dirname "$0")/_comun.sh"
exigir_env

ARCHIVO="${1:-}"
if [[ -z "$ARCHIVO" || ! -f "$ARCHIVO" ]]; then
  echo "Uso: $0 <archivo.dump>" >&2
  exit 1
fi

if [[ -z "${CONFIRMAR:-}" ]]; then
  read -r -p "Esto borra los datos actuales y los reemplaza por $ARCHIVO. Escribe SI para continuar: " respuesta
  [[ "$respuesta" == "SI" ]] || { echo "Cancelado."; exit 1; }
fi

echo "==> Deteniendo API y worker"
dc stop api worker

echo "==> Restaurando"
dc exec -T db psql -U beematch -d beematch -q -v ON_ERROR_STOP=1 \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
dc exec -T db pg_restore -U beematch -d beematch --no-owner --exit-on-error < "$ARCHIVO"

echo "==> Levantando API y worker"
dc start api worker
echo "Restauración terminada."
