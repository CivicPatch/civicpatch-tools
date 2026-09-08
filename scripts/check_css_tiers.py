#!/usr/bin/env python3
"""Guard the CSS core/shell split described in .scratch/2026-09-07-plan-css-core-and-shell.md.

The rules below are all stated in tokens.css's own header. They grew a fourth,
redundant token tier once already because nothing checked them.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "civicpatch.org/src/frontend"
SHELL = ROOT / "css"  # tokens, elements, layout, styles, utilities
TOKENS = SHELL / "tokens.css"

# !important is a specificity fight. Every one left is a known debt; the number
# may fall, never rise. @layer removed the ones that were fighting the base layer;
# what is left fights third-party CSS, which is unlayered and so outranks us.
IMPORTANT_CEILING = 14

ELEMENT = r"a|p|ul|ol|li|h[1-6]|table|thead|tbody|tr|td|th|button|input|select|textarea|label|form|fieldset|legend|section|article|aside|nav|main|header|footer|dialog|details|summary|img|svg|pre|code|figure|blockquote"
BARE_SELECTOR = re.compile(rf"^(?:{ELEMENT})(?:[\s,{{:>+~]|$)")


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def top_level_bare_selectors(text):
    """Only depth 0 counts. A bare `button` nested inside `.review-modal { … }` is
    scoped by its parent — flagging it is the false positive that gets a check ignored."""
    # strip comments across the whole file first: a line inside a block comment can
    # start with a word like "table" and read exactly like a selector
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    depth, hits = 0, []
    for raw in stripped.splitlines():
        line = raw.strip()
        if depth == 0 and BARE_SELECTOR.match(line):
            hits.append(line.rstrip("{").strip())
        depth += raw.count("{") - raw.count("}")
    return hits


def sources():
    for p in ROOT.rglob("*.css"):
        if "build" in p.parts or "node_modules" in p.parts or "generated" in p.parts:
            continue
        yield p


def main() -> int:
    failures = []
    important = 0

    for p in sources():
        text = p.read_text(errors="ignore")
        rel = p.relative_to(ROOT)
        # declarations only — a comment explaining why an `!important` was removed
        # must not count as one, or the check punishes the fix
        important += strip_comments(text).count("!important")

        if p != TOKENS and "--tone-" in text:
            failures.append(f"{rel}: references a --tone-* primitive; use a semantic token")
        if "--pico-" in text or "--civ-" in text:
            failures.append(f"{rel}: uses a retired --pico-*/--civ-* name")
        if SHELL not in p.parents:
            for hit in top_level_bare_selectors(text):
                failures.append(f"{rel}: top-level bare element selector {hit!r}; scope it")

    for p in ROOT.rglob("*.ts"):
        if "build" in p.parts or "node_modules" in p.parts:
            continue
        t = p.read_text(errors="ignore")
        if "--tone-" in t or "--pico-" in t or "--civ-" in t:
            failures.append(f"{p.relative_to(ROOT)}: retired or primitive token name in TS")

    if important > IMPORTANT_CEILING:
        failures.append(
            f"!important count rose to {important} (ceiling {IMPORTANT_CEILING}). "
            "Lower the ceiling when you remove one; never raise it."
        )

    for f in failures:
        print(f"CSS tier check: {f}", file=sys.stderr)
    if not failures:
        print(f"CSS tier check: ok ({important} !important, ceiling {IMPORTANT_CEILING})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
