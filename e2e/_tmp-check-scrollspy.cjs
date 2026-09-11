const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });

  await page.goto("http://localhost:8000/blog/building-a-directory-of-local-representatives", { waitUntil: "networkidle" });

  const before = await page.evaluate(() =>
    [...document.querySelectorAll(".blog-post__toc nav a")].map(a => a.classList.contains("blog-post__toc-link--active"))
  );
  console.log("active states before scroll:", before);

  await page.locator("#project").scrollIntoView();
  await page.waitForTimeout(500);

  const after = await page.evaluate(() =>
    [...document.querySelectorAll(".blog-post__toc nav a")].map(a => ({
      text: a.textContent,
      active: a.classList.contains("blog-post__toc-link--active"),
    }))
  );
  console.log("active states after scrolling to #project:", JSON.stringify(after, null, 2));
  console.log("console/page errors:", JSON.stringify(errors));

  await page.screenshot({ path: "/tmp/claude-1000/-home-witch-civicpatch-tools/b6123303-ff09-4667-b13c-2ebd70b05a19/scratchpad/scrollspy-check.png" });

  await browser.close();
})();
