/**
 * The build subsets the webfonts to icons.js, so an icon used but not declared there
 * renders as nothing. This catches the ordinary case: a literal `fa-solid fa-x` class.
 *
 * It deliberately cannot catch names assembled at runtime — `fa-arrow-${dir}` and the
 * ATTENTION_COPY / FIELD_ICON / FALLBACK_ICONS tables. Those are declared in icons.js
 * by hand, and the regex below skips them rather than reporting a half-read name.
 */

import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { BRANDS, REGULAR, SOLID } from "../icons.js";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
// tests/ ships no markup, and icons.js is the declaration rather than a usage — both
// mention icon classes in prose, which would otherwise read as undeclared usages.
const SKIP = new Set(["node_modules", "build", "generated", "__pycache__", "tests"]);
const SKIP_FILES = new Set(["icons.js"]);
const EXTENSIONS = [".html", ".js", ".ts"];

const DECLARED: Record<string, string[]> = {
  solid: SOLID,
  regular: REGULAR,
  brands: BRANDS,
};

// The name must end in an alphanumeric, so `fa-arrow-${dir}` matches nothing at all
// rather than yielding the truncated "arrow-".
const USAGE = /fa-(solid|regular|brands) fa-([a-z0-9-]*[a-z0-9])(?![a-z0-9-])/g;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    if (SKIP.has(entry) || SKIP_FILES.has(entry)) return [];
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return EXTENSIONS.some((ext) => entry.endsWith(ext)) ? [path] : [];
  });
}

describe("icon manifest", () => {
  it("declares every icon the source names literally", () => {
    const undeclared: string[] = [];

    for (const file of sourceFiles(ROOT)) {
      const source = readFileSync(file, "utf8");
      for (const [, style, name] of source.matchAll(USAGE)) {
        if (!DECLARED[style].includes(name)) {
          undeclared.push(`${style} "${name}" — ${relative(ROOT, file)}`);
        }
      }
    }

    expect(undeclared).toEqual([]);
  });

  it("has no duplicate declarations", () => {
    for (const [style, names] of Object.entries(DECLARED)) {
      expect(names, style).toEqual([...new Set(names)]);
    }
  });
});
