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
      //
      // An absolute budget, not a ratio. The noise scales with how much *text* is
      // on screen; a ratio scales with page area, and these captures run 900px to
      // 4755px tall. The same 2973 differing pixels was 0.0023 on /login and
      // 0.0004 on review-modal — so a ratio judged the short pages five times
      // harder for being short, and /login failed while nothing was wrong with it.
      //
      // 4000 is the observed floor (~3000) plus headroom. It is a few words of
      // text, so a real copy or colour change still trips it.
      maxDiffPixels: 4000,
      animations: "disabled",
    },
  },
});
