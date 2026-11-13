const HIDDEN_ELEMENTS = "script, style, noscript, template, svg, head";
const BLOCK_ELEMENTS =
  "address, article, aside, blockquote, br, dd, div, dl, dt, fieldset, figcaption, figure, footer, " +
  "form, h1, h2, h3, h4, h5, h6, header, hr, li, main, nav, ol, p, pre, section, table, td, th, tr, ul";

export function tidyLines(text: string): string {
  const lines = text.split("\n").map((line) => line.replace(/\s+/g, " ").trim());
  const kept: string[] = [];
  for (const line of lines) {
    if (line || kept[kept.length - 1]) kept.push(line);
  }
  return kept.join("\n").trim();
}

export function pageText(fetchedHtml: string): string {
  const doc = new DOMParser().parseFromString(fetchedHtml, "text/html");
  doc.querySelectorAll(HIDDEN_ELEMENTS).forEach((element) => element.remove());
  doc.querySelectorAll(BLOCK_ELEMENTS).forEach((element) => element.after("\n"));
  return tidyLines(doc.body?.textContent ?? "");
}
