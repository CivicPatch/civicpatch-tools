import { defineConfig, devices } from "@playwright/test";

// Separate from playwright.config.js on purpose: the behaviour suite and the
// visual oracle want opposite settings. Behaviour tests run with slowMo and
// trace-on to be debuggable; screenshots want none of that, and a stray 300ms
// slowMo turns a 30-second run into minutes.
export default defineConfig({
  testDir: "./visual",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  // Its own directory, not the behaviour suite's test-results/ — that one is
  // root-owned on this box from a docker CI run and unwritable.
  outputDir: "./visual-results",
  // Baselines live next to the spec rather than in a per-OS directory. The
  // stack is dockerised and everyone runs it the same way; a platform suffix
  // would only invite committing two sets that drift apart.
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  use: {
    // Spread first — Desktop Chrome carries its own viewport and would silently
    // undo the settings below if it came last.
    ...devices["Desktop Chrome"],
    baseURL: process.env.BASE_URL ?? "http://localhost:8100",
    trace: "off",
    screenshot: "off",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    // The app drives theming off <html data-theme>, but the navbar falls back to
    // prefers-color-scheme before its first render. Pin it so that fallback is
    // never what a baseline captured.
    colorScheme: "light",
  },
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      // Anti-aliasing differs by a pixel or two between runs on the same box.
      // Strict enough to catch a colour or spacing change, loose enough not to
      // cry wolf — tighten if it proves noisy in the other direction.
      maxDiffPixelRatio: 0.001,
      animations: "disabled",
    },
  },
});
