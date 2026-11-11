#!/usr/bin/env bash
# Despliega (o actualiza) BeeMatch en este servidor.
#
#   ./scripts/aws/desplegar.sh              # trae la rama actual, reconstruye y reinicia
#   RAMA=main ./scripts/aws/desplegar.sh    # cambia de rama antes
#   SIN_GIT=1 ./scripts/aws/desplegar.sh    # no toca git (el código ya está aquí)
#
# Antes de tocar nada hace un respaldo de la base si ya existe una en marcha,
# así una actualización mala siempre tiene vuelta atrás (ver restaurar.sh).
source "$(dirname "$0")/_comun.sh"
exigir_env

cd "$RAIZ"

if [[ -z "${SIN_GIT:-}" ]]; then
  if [[ -n "${RAMA:-}" ]]; then
    git fetch origin "$RAMA"
    git checkout "$RAMA"
  fi
  git pull --ff-only
fi
echo "==> Versión: $(git -C "$RAIZ" log -1 --format='%h %s' 2>/dev/null || echo 'sin git')"

if dc ps --status running --services 2>/dev/null | grep -qx db; then
  echo "==> Respaldo previo"
  "$RAIZ/scripts/aws/respaldar.sh"
fi

echo "==> Construyendo y levantando"
dc up -d --build --remove-orphans

echo "==> Esperando a que la API esté sana"
for _ in $(seq 1 40); do
  estado="$(dc ps --format '{{.Service}} {{.Health}}' | awk '$1=="api"{print $2}')"
  [[ "$estado" == "healthy" ]] && break
  sleep 3
done
if [[ "${estado:-}" != "healthy" ]]; then
  echo "La API no quedó sana. Últimas líneas del log:" >&2
  dc logs --tail=40 api >&2
  exit 1
fi

dc ps
echo
echo "Estado de la API: $(dc exec -T api python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health/ready').read().decode())")"

echo "==> Limpiando imágenes sin uso"
docker image prune -f >/dev/null
echo "Despliegue terminado."
