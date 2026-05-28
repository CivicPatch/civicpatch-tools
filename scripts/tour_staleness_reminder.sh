#!/usr/bin/env bash
# Check staged .tour files for stale steps (missing files, lines past EOF,
# patterns no longer in file). Prints a reminder if any are stale. Always
# exits 0 — this is a nudge, not a gate.
set -euo pipefail

if ! command -v jq &>/dev/null; then
    exit 0
fi

staged_tours=$(git diff --cached --name-only | grep '^\.tours/.*\.tour$' || true)

if [ -z "$staged_tours" ]; then
    exit 0
fi

stale=0

while IFS= read -r tour_file; do
    [ -f "$tour_file" ] || continue

    problems=()

    step_count=$(jq '.steps | length' "$tour_file")

    for i in $(seq 0 $((step_count - 1))); do
        step_title=$(jq -r ".steps[$i].title" "$tour_file")
        file=$(jq -r ".steps[$i].file // empty" "$tour_file")
        line=$(jq -r ".steps[$i].line // empty" "$tour_file")
        pattern=$(jq -r ".steps[$i].pattern // empty" "$tour_file")

        if [ -n "$file" ]; then
            if [ ! -f "$file" ]; then
                problems+=("  \"$step_title\": file \"$file\" not found")
                continue
            fi
            if [ -n "$line" ] && [ "$line" -gt 0 ] 2>/dev/null; then
                file_lines=$(wc -l < "$file")
                if [ "$line" -gt "$file_lines" ]; then
                    problems+=("  \"$step_title\": line $line past EOF (\"$file\" has $file_lines lines)")
                fi
            fi
        fi

        if [ -n "$pattern" ]; then
            if [ -n "$file" ] && [ -f "$file" ]; then
                if ! grep -qF "$pattern" "$file" 2>/dev/null; then
                    problems+=("  \"$step_title\": pattern \"$pattern\" not found in \"$file\"")
                fi
            fi
        fi
    done

    if [ ${#problems[@]} -gt 0 ]; then
        stale=1
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  $tour_file has stale steps:"
        echo ""
        for p in "${problems[@]}"; do
            echo "$p"
        done
        echo ""
        echo "  Ask an LLM to update the stale steps in this tour file."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi
done <<< "$staged_tours"

if [ "$stale" = "1" ]; then
    echo ""
fi

exit 0