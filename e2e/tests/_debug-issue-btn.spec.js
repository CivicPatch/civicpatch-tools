import { test } from "../fixtures/index.js";
import { READ_ONLY_JURISDICTION_OCDID } from "../fixtures/db.js";

test("debug report issue button whitespace", async ({ adminPage: page }) => {
  await page.goto(`/${READ_ONLY_JURISDICTION_OCDID}`);
  await page.waitForTimeout(700);
  const box = await page.locator("a.btn-quiet").boundingBox();
  console.log("box:", JSON.stringify(box));
  await page.screenshot({ path: "/tmp/claude-1000/-home-witch-civicpatch-tools/7f34a22d-ef26-49a3-be44-ea7939fd9c9b/scratchpad/issue-btn-zoom.png", clip: { x: Math.max(0, box.x - 40), y: Math.max(0, box.y - 40), width: box.width + 300, height: box.height + 80 } });
});
