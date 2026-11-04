#!/usr/bin/env bash
# The suites a commit touches, run at once: they are independent, and in sequence a shared/
# change took ~47 s against ~30 s for the slowest of them. Each task's output is kept whole and
# printed when it ends, so a failure reads as it did before.
set -e
trap 'echo; echo "Tests failed. To skip: git commit --no-verify"' ERR

changed=$(git diff --cached --name-only)

touches_civicpatch=$(echo "$changed" | grep -q "^pipelines/\|^shared/" && echo 1 || echo 0)
touches_shared=$(echo "$changed" | grep -q "^shared/" && echo 1 || echo 0)
touches_api=$(echo "$changed" | grep -q "^civicpatch\.org/\|^shared/" && echo 1 || echo 0)

tasks=()
if [ "$touches_civicpatch" = "1" ]; then
    tasks+=(tpipes typecheck-pipelines)
fi
if [ "$touches_shared" = "1" ]; then
    tasks+=(pytest-shared)
fi
if [ "$touches_api" = "1" ]; then
    tasks+=(tcp typecheck-cp)
fi
[ "${#tasks[@]}" -eq 0 ] && exit 0

logs=$(mktemp -d)
trap 'rm -rf "$logs"' EXIT
pids=()
for task in "${tasks[@]}"; do
    mise run "$task" > "$logs/$task" 2>&1 &
    pids+=($!)
done

failed=0
for i in "${!tasks[@]}"; do
    task=${tasks[$i]}
    if wait "${pids[$i]}"; then
        echo "$task: ok ($(grep -v '^[[:space:]]*$' "$logs/$task" | tail -n 1))"
    else
        failed=1
        echo; echo "=== $task failed ==="; cat "$logs/$task"
    fi
done

if [ "$failed" = "1" ]; then
    echo; echo "Tests failed. To skip: git commit --no-verify"
    exit 1
fi
