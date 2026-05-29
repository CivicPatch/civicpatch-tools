import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto('http://localhost:8000/config-editor-demo');
// Close the first open section
const openDetails = page.locator('details[open]').first();
await openDetails.locator('summary').click();
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/closed-sections.png' });
await browser.close();
