const { chromium } = require('@playwright/test');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:8000/config-editor-demo');
  await page.waitForTimeout(500);
  // Focus the first action button directly
  await page.locator('.config-editor__action-btn').first().focus();
  await page.waitForTimeout(200);
  await page.screenshot({ path: '/tmp/focus.png' });
  await browser.close();
  console.log('done');
})();
