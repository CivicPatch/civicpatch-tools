#!/bin/sh
set -e

Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &

sleep 1

exec "$@"