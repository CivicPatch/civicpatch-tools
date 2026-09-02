// Subsets the Font Awesome webfonts to the icons in icons.js and emits one stylesheet
// for them. The shipped solid face is ~1400 glyphs; the app uses about fifty, and woff2
// is already compressed so nothing downstream can recover the difference.
//
// Output goes to generated/fontawesome/ (gitignored) and is imported by navbar.js like
// any other stylesheet, so Vite hashes and inlines the font URLs as it always has.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import subsetFont from "subset-font";

import { BRANDS, REGULAR, SOLID } from "../icons.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const FA = join(HERE, "../node_modules/@fortawesome/fontawesome-free");
const OUT = join(HERE, "../generated/fontawesome");

const FACES = [
  { style: "solid", names: SOLID, font: "fa-solid-900", css: "solid.min.css", glyphs: "fontawesome.min.css" },
  { style: "regular", names: REGULAR, font: "fa-regular-400", css: "regular.min.css", glyphs: "fontawesome.min.css" },
  { style: "brands", names: BRANDS, font: "fa-brands-400", css: "brands.min.css", glyphs: "brands.min.css" },
];

// FA writes each glyph as a CSS string escape, and aliases share one selector list:
//   .fa-circle-info,.fa-info-circle{--fa:"\f05a"}   hex escape
//   .fa-plus{--fa:"\+"}                             escaped literal, U+002B
// Missing either form drops that glyph from the subset with no error.
const GLYPH_RULE =
  /((?:\.fa-[a-z0-9-]+,)*\.fa-[a-z0-9-]+)\{--fa:"\\(?:([0-9a-f]{1,6})\s?|(.))"\}/g;

export function parseCodepoints(css) {
  const table = new Map();
  for (const [, selectors, hex, literal] of css.matchAll(GLYPH_RULE)) {
    const codepoint = hex ? parseInt(hex, 16) : literal.codePointAt(0);
    for (const [, name] of selectors.matchAll(/\.fa-([a-z0-9-]+)/g)) {
      table.set(name, codepoint);
    }
  }
  return table;
}

const readCss = (file) => readFile(join(FA, "css", file), "utf8");

// FA's per-style sheet is kept as-is for its family and style rules; only the src is
// repointed at the subset sitting beside this file, and its own glyph table dropped.
function styleRules(css, font) {
  return css
    .replace(GLYPH_RULE, "")
    .replace(`url(../webfonts/${font}.woff2)`, `url(./${font}.woff2)`);
}

function glyphRules(names, table) {
  return names
    .map((name) => `.fa-${name}{--fa:"\\${table.get(name).toString(16)}"}`)
    .join("");
}

async function buildFace(face) {
  const table = parseCodepoints(await readCss(face.glyphs));
  const unknown = face.names.filter((name) => !table.has(name));
  if (unknown.length) {
    throw new Error(
      `icons.js lists ${face.style} icons Font Awesome does not define: ${unknown.join(", ")}`,
    );
  }

  const original = await readFile(join(FA, "webfonts", `${face.font}.woff2`));
  const text = face.names.map((n) => String.fromCodePoint(table.get(n))).join("");
  const subset = await subsetFont(original, text, { targetFormat: "woff2" });
  await writeFile(join(OUT, `${face.font}.woff2`), subset);

  console.log(
    `  ${face.style.padEnd(8)} ${String(face.names.length).padStart(3)} icons  ` +
      `${original.length.toLocaleString().padStart(8)} -> ${subset.length.toLocaleString()} bytes`,
  );
  return styleRules(await readCss(face.css), face.font) + glyphRules(face.names, table);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  console.log("Subsetting Font Awesome:");

  // The core sheet holds the style-agnostic rules (.fa sizing, .fa-spin, layering) plus
  // the whole free glyph table; the rules are wanted, the table is replaced per face.
  const core = (await readCss("fontawesome.min.css")).replace(GLYPH_RULE, "");
  const faces = [];
  for (const face of FACES) {
    faces.push(await buildFace(face));
  }

  await writeFile(join(OUT, "icons.css"), [core, ...faces].join("\n"));
}

await main();
