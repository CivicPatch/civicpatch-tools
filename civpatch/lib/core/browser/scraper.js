// fetch-content.js
const { chromium } = require('playwright');

async function fetchContent(url) {
  const browser = await chromium.launch({
    headless: true,
    args: ['--single-process']
  });

  try {
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });

    const page = await context.newPage();

    // Navigate with minimal wait
    await page.goto(url, { waitUntil: 'networkidle', timeout: 10000 });

    // Try multiple wait conditions
    try {
      await page.waitForLoadState('networkidle', { timeout: 5000 });
    } catch (e) {
      console.error('Network idle timeout, continuing anyway...');
    }

    // Get content regardless of wait status
    const content = await page.content();

    // Output the content to stdout
    console.log(content);

    return 0;
  } catch (error) {
    console.error('Error during navigation:', error);

    // Still try to get content even if there was an error
    try {
      const content = await page.evaluate(() => document.documentElement.outerHTML);
      console.log(content);
      return 0;
    } catch (e) {
      console.error('Failed to get content:', e);
      return 1;
    }
  } finally {
    await browser.close();
  }
}

// Get URL from command line argument
const url = process.argv[2];
if (!url) {
  console.error('Please provide a URL as an argument');
  process.exit(1);
}

fetchContent(url).then(exitCode => process.exit(exitCode));
