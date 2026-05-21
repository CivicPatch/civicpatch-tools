// Visual sanity check for the email-login component — confirms the
// "Wrong email?" reset link is actually visible after Send code.
// Temporary; remove after the auth UI is settled.

import { test, expect } from "@playwright/test";

test("Wrong email? button is visible after sending code", async ({ page }) => {
  await page.goto("http://localhost:8000/login");

  // Fill email, send OTP
  await page.fill("#email-login-email", "vischeck@example.com");
  await page.click('button[type="submit"]');

  // Wait for code input to appear (means we transitioned to "enter-code" step)
  await page.waitForSelector("#email-login-code", { timeout: 5000 });

  // The reset button should be in DOM and visible
  const reset = page.locator(".email-login__reset");
  await expect(reset).toBeVisible();
  await expect(reset).toHaveText(/Wrong email/);

  // Capture computed styles for diagnosis
  const styles = await reset.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      color: cs.color,
      background: cs.backgroundColor,
      display: cs.display,
      visibility: cs.visibility,
      opacity: cs.opacity,
      fontSize: cs.fontSize,
      width: cs.width,
      height: cs.height,
    };
  });
  console.log("computed styles:", JSON.stringify(styles, null, 2));

  // Screenshot for visual verification
  await page.screenshot({ path: "test-results/login-after-otp.png", fullPage: true });
});
