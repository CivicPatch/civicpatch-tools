import { chromium } from "@playwright/test";
const OUT = "/tmp/claude-1000/-home-witch-civicpatch-tools/b72a7457-a8fc-4a28-ad6f-8b9aeddb97e8/scratchpad";
const b = await chromium.launch();
for (const theme of ["light", "dark"]) {
  const p = await b.newPage({ viewport: { width: 1000, height: 700 } });
  await p.goto(`file://${OUT}/step1-check.html`);
  await p.evaluate((t) => (document.documentElement.dataset.theme = t), theme);
  await p.waitForTimeout(600);
  const hs = await p.$$eval(".field-control__input, .field-control__x, .field-control__add, .field-control__division-select, .field-control__division-input",
    els => [...new Set(els.map(e => Math.round(e.getBoundingClientRect().height * 10) / 10))]);
  console.log(theme, "control heights:", hs.join(", "));
  await p.screenshot({ path: `${OUT}/step1-${theme}.png` });
  await p.close();
}
await b.close();
