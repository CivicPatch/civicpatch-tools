#!/bin/sh
set -e
export DISPLAY=:99

echo "Starting Xvfb in background..."
echo "Running as $(id -u) $(id -g)"

[ -f /tmp/.X99-lock ] && rm -f /tmp/.X99-lock

# Wait for Xvfb to be ready
Xvfb :99 -screen 0 1024x768x24  &

# Wait for Xvfb
MAX_ATTEMPTS=120 # About 60 seconds
COUNT=0
echo -n "Waiting for Xvfb to be ready..."
while ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; do
  echo -n "."
  sleep 0.50s
  COUNT=$(( COUNT + 1 ))
  if [ "${COUNT}" -ge "${MAX_ATTEMPTS}" ]; then
    echo "  Gave up waiting for X server on ${DISPLAY}"
    exit 1
  fi
done
echo "  Done - Xvfb is ready!"

# Trust Caddy's internal CA in development
if [ "$CIVICPATCH_ENV" = "development" ]; then
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
  exec "$@"
fi