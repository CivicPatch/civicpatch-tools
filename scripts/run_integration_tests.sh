#!/usr/bin/env bash
set -e
trap 'echo; echo "Integration tests failed. To skip: git push --no-verify"' ERR

changed=$(git diff --name-only @{u}..HEAD 2>/dev/null || git diff --name-only HEAD~1..HEAD)

touches_api=$(echo "$changed" | grep -q "^civicpatch\.org/\|^shared/" && echo 1 || echo 0)

if [ "$touches_api" = "1" ]; then
    mise run tcp-integration
fi
