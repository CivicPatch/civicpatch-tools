#!/bin/sh
set -e
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
export DISPLAY=:99
# Wait for Xvfb to be ready
for i in $(seq 1 10); do
  if xdpyinfo -display :99 > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
exec "$@"