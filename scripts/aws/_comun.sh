#!/usr/bin/env bash
# Funciones compartidas por los scripts de scripts/aws. Se carga con `source`.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$RAIZ/.env.production}"
export ENV_FILE

# docker compose apuntando siempre al archivo de producción y a su .env.
dc() {
  docker compose -f "$RAIZ/docker-compose.prod.yml" --env-file "$ENV_FILE" "$@"
}

exigir_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Falta $ENV_FILE. Cópialo de .env.production.example y complétalo." >&2
    exit 1
  fi
}
