#!/usr/bin/env bash
# hotspot = commits touching the file in the window x the file's total cyclomatic complexity
set -euo pipefail
cd "$(dirname "$0")/.."

days="${1:-180}"
top="${2:-20}"
packages=(civicpatch.org/src pipelines/src shared/src)
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

git log --since="${days}.days" --name-only --format= -- "${packages[@]/%//*.py}" \
  | grep '\.py$' | sort | uniq -c | awk '{print $2"\t"$1}' > "$work/churn.tsv"
uvx radon@6.0.1 cc -s -j "${packages[@]}" > "$work/cc.json"

python3 -I - "$work/cc.json" "$work/churn.tsv" "$top" "$days" <<'PY'
import json, sys

cc = json.load(open(sys.argv[1]))
churn = dict(line.split("\t") for line in open(sys.argv[2]).read().splitlines())
top, days = int(sys.argv[3]), sys.argv[4]

complexity = {f: sum(b["complexity"] for b in blocks) for f, blocks in cc.items() if isinstance(blocks, list)}
rows = sorted(((int(churn.get(f, 0)) * c, int(churn.get(f, 0)), c, f) for f, c in complexity.items()), reverse=True)

print(f"hotspot = commits in last {days} days x cyclomatic complexity\n")
print("hotspot\tcommits\tcomplexity\tfile")
for hotspot, commits, total, path in rows[:top]:
    print(f"{hotspot}\t{commits}\t{total}\t{path}")
PY
