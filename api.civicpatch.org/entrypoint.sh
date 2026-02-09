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

  # Timeout configuration (in seconds)
  TIMEOUT=60
  WAIT_INTERVAL=2
  ELAPSED=0

  # Wait for Caddy root certificate to exist
  while [ ! -f "$ROOT_CERT_PATH" ]; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
      echo "[development] Timeout reached: Caddy root certificate not found. Continuing without trusting Caddy root certificate."
      break
    fi
    echo "[development] Waiting for Caddy root certificate..."
    sleep "$WAIT_INTERVAL"
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
  done

  # If the certificate exists, install it
  if [ -f "$ROOT_CERT_PATH" ]; then
    cp "$ROOT_CERT_PATH" "$DEST_CERT_PATH" || echo "[development] cp failed, continuing..."
    update-ca-certificates || echo "[development] update-ca-certificates failed, continuing..."

    # Append to certifi bundle for Python
    CERTIFI_PATH=$(python -c "import certifi; print(certifi.where())")
    cat "$DEST_CERT_PATH" >> "$CERTIFI_PATH" || echo "[development] certifi append failed, continuing..."

    echo "[development] Caddy root certificate trusted."
  else
    echo "[development] Skipping Caddy root certificate trust setup."
  fi
fi

# Drop privileges and run the command as civicpatch_user
exec su civicpatch_user -c "$*"