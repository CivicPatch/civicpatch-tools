#!/usr/bin/env bash
set -e
trap 'echo; echo "Tests failed. To skip: git commit --no-verify"' ERR

changed=$(git diff --cached --name-only)

touches_civicpatch=$(echo "$changed" | grep -q "^pipelines/\|^shared/" && echo 1 || echo 0)
touches_shared=$(echo "$changed" | grep -q "^shared/" && echo 1 || echo 0)
touches_api=$(echo "$changed" | grep -q "^civicpatch\.org/\|^shared/" && echo 1 || echo 0)

if [ "$touches_civicpatch" = "1" ]; then
    mise run tcp
fi

if [ "$touches_shared" = "1" ]; then
    mise run pytest-shared
fi

if [ "$touches_api" = "1" ]; then
    mise run tapi
fi
