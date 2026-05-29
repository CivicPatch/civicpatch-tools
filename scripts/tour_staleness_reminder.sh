#!/usr/bin/env bash
# Check tours for stale steps. Runs whenever:
#   - a .tour file itself is staged, OR
#   - any file referenced by a tour is staged
#
# A tour that maps a code path becomes wrong silently when that code moves —
# this hook is a nudge to update the tour. Always exits 0 (nudge, not gate).
set -euo pipefail

if ! command -v jq &>/dev/null; then
    exit 0
fi

if [ ! -d .tours ]; then
    exit 0
fi

staged=$(git diff --cached --name-only)
[ -z "$staged" ] && exit 0

# Find tours to check: any tour whose .file references include a staged path,
# plus any tour that is itself staged.
tours_to_check=()
for tour_file in .tours/*.tour; do
    [ -f "$tour_file" ] || continue

    # If the tour itself is staged, check it.
    if echo "$staged" | grep -qxF "$tour_file"; then
        tours_to_check+=("$tour_file")
        continue
    fi

    # Otherwise: does it reference any staged file?
    referenced=$(jq -r '.steps[].file // empty' "$tour_file" 2>/dev/null || true)
    while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        if echo "$staged" | grep -qxF "$ref"; then
            tours_to_check+=("$tour_file")
            break
        fi
    done <<< "$referenced"
done

[ ${#tours_to_check[@]} -eq 0 ] && exit 0

stale=0

for tour_file in "${tours_to_check[@]}"; do
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

        if [ -n "$pattern" ] && [ -n "$file" ] && [ -f "$file" ]; then
            if ! grep -qF "$pattern" "$file" 2>/dev/null; then
                problems+=("  \"$step_title\": pattern \"$pattern\" not found in \"$file\"")
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
done

[ "$stale" = "1" ] && echo ""
exit 0
