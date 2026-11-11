#!/usr/bin/env bash
# Guarda y recupera .env.production en AWS Systems Manager Parameter Store
# (SecureString, cifrado con KMS). Cubre el gestor de secretos del diseño (C23)
# sin pagar Secrets Manager (~0,40 USD por secreto al mes; Parameter Store estándar es gratis).
#
#   ./scripts/aws/secretos-ssm.sh subir     # .env.production  ->  /beematch/prod/*
#   ./scripts/aws/secretos-ssm.sh bajar     # /beematch/prod/*  ->  .env.production (chmod 600)
#
# Variables: PREFIJO_SSM (por defecto /beematch/prod), AWS_REGION.
# La instancia necesita un rol con ssm:PutParameter / ssm:GetParametersByPath (y
# kms:Decrypt); desde tu máquina basta con tus credenciales de AWS.
#
# Sirve para no perder los secretos si se pierde la instancia, y para recrear el
# servidor sin copiar archivos a mano. Los valores vacíos se omiten.
source "$(dirname "$0")/_comun.sh"

PREFIJO="${PREFIJO_SSM:-/beematch/prod}"
command -v aws >/dev/null || { echo "Falta la CLI de AWS (aws)." >&2; exit 1; }

case "${1:-}" in
  subir)
    exigir_env
    total=0
    while IFS= read -r linea || [[ -n "$linea" ]]; do
      [[ "$linea" =~ ^[[:space:]]*# || -z "${linea//[[:space:]]/}" || "$linea" != *=* ]] && continue
      clave="${linea%%=*}"
      valor="${linea#*=}"
      [[ -z "$valor" ]] && continue
      aws ssm put-parameter --name "$PREFIJO/$clave" --value "$valor" \
        --type SecureString --overwrite --only-show-errors >/dev/null
      total=$((total + 1))
    done < "$ENV_FILE"
    echo "Subidos $total parámetros a $PREFIJO/"
    ;;
  bajar)
    if [[ -e "$ENV_FILE" && -z "${SOBRESCRIBIR:-}" ]]; then
      echo "$ENV_FILE ya existe. Usa SOBRESCRIBIR=1 para reemplazarlo." >&2
      exit 1
    fi
    umask 077
    aws ssm get-parameters-by-path --path "$PREFIJO" --with-decryption --recursive \
      --query 'Parameters[].[Name,Value]' --output text \
      | while IFS=$'\t' read -r nombre valor; do
          echo "${nombre##*/}=$valor"
        done > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "Escrito $ENV_FILE con $(wc -l < "$ENV_FILE" | tr -d ' ') variables."
    ;;
  *)
    echo "Uso: $0 subir|bajar" >&2
    exit 1
    ;;
esac
