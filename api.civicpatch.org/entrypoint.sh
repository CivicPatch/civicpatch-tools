#!/bin/sh
set -euo pipefail

echo "Running entrypoint.sh script..."

python database_operations/migrate.py up

echo "App start - migrations completed."

# Trust Caddy's internal CA in development

if [ "$APP_ENVIRONMENT" = "development" ]; then
  echo "[development] Checking for Caddy root certificate..."
  ROOT_CERT_PATH="/development/caddy/data/caddy/pki/authorities/local/root.crt"
  DEST_CERT_PATH="/usr/local/share/ca-certificates/caddy-root.crt"
  SYSTEM_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"

  # Wait for Caddy root certificate to exist
  while [ ! -f "$ROOT_CERT_PATH" ]; do
    echo "[development] Waiting for Caddy root certificate..."
    sleep 2
  done

  # Install Caddy root certificate
  cp "$ROOT_CERT_PATH" "$DEST_CERT_PATH" || echo "[development] cp failed, continuing..."
  update-ca-certificates || echo "[development] update-ca-certificates failed, continuing..."

  # Append to certifi bundle for Python
  CERTIFI_PATH=$(python -c "import certifi; print(certifi.where())")
  cat "$DEST_CERT_PATH" >> "$CERTIFI_PATH" || echo "[development] certifi append failed, continuing..."

  echo "[development] Caddy root certificate trusted (or step skipped)."

  # Set environment variables for requests and httpx
  ENV_VARS="REQUESTS_CA_BUNDLE=$SYSTEM_CA_BUNDLE SSL_CERT_FILE=$SYSTEM_CA_BUNDLE"

  # Drop privileges and run the command as civicpatch_user
  exec su civicpatch_user -c "$ENV_VARS $*"
else
  exec su civicpatch_user -c "$*"
fi
