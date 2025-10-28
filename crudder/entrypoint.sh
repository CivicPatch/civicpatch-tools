#!/bin/sh
set -euo pipefail

echo "Running entrypoint.sh script..."

python database_operations/migrate.py up

echo "App start - migrations completed."

exec "$@"
