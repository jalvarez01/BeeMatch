#!/usr/bin/env bash
# Respaldo de la base de datos (pg_dump en formato personalizado).
#
#   ./scripts/aws/respaldar.sh
#
# Deja el archivo en $DESTINO (por defecto ./respaldos) y conserva los últimos
# $CONSERVAR (7). Si BUCKET_RESPALDOS está definido y hay `aws` instalado,
# también lo sube a S3 (la instancia necesita permiso de escritura en el bucket).
#
# Para programarlo cada noche a las 2:00:
#   (crontab -l; echo "0 2 * * * /opt/beematch/app/scripts/aws/respaldar.sh >> /opt/beematch/respaldos/cron.log 2>&1") | crontab -
source "$(dirname "$0")/_comun.sh"
exigir_env

DESTINO="${DESTINO:-$RAIZ/respaldos}"
CONSERVAR="${CONSERVAR:-7}"
mkdir -p "$DESTINO"

ARCHIVO="$DESTINO/beematch-$(date +%Y%m%d-%H%M%S).dump"
dc exec -T db pg_dump -U beematch -d beematch -Fc > "$ARCHIVO"

if [[ ! -s "$ARCHIVO" ]]; then
  rm -f "$ARCHIVO"
  echo "El respaldo salió vacío." >&2
  exit 1
fi
echo "Respaldo: $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))"

if [[ -n "${BUCKET_RESPALDOS:-}" ]] && command -v aws >/dev/null; then
  aws s3 cp "$ARCHIVO" "s3://$BUCKET_RESPALDOS/$(basename "$ARCHIVO")" --only-show-errors
  echo "Subido a s3://$BUCKET_RESPALDOS/"
fi

# Conserva solo los más recientes.
ls -1t "$DESTINO"/beematch-*.dump | tail -n +"$((CONSERVAR + 1))" | xargs -r rm -f
