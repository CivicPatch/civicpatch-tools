#!/usr/bin/env bash
set -e
trap 'echo; echo "Tests failed. To skip: git commit --no-verify"' ERR

changed=$(git diff --cached --name-only)

touches_civicpatch=$(echo "$changed" | grep -q "^pipelines/\|^shared/" && echo 1 || echo 0)
touches_shared=$(echo "$changed" | grep -q "^shared/" && echo 1 || echo 0)
touches_api=$(echo "$changed" | grep -q "^civicpatch\.org/\|^shared/" && echo 1 || echo 0)
touches_worker=$(echo "$changed" | grep -q "^worker/\|^shared/" && echo 1 || echo 0)

if [ "$touches_civicpatch" = "1" ]; then
    mise run tpipes
    mise run typecheck-pipelines
fi

if [ "$touches_shared" = "1" ]; then
    mise run pytest-shared
fi

if [ "$touches_api" = "1" ]; then
    mise run tcp
    mise run typecheck-cp
fi
