import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  // Not the default `test-results/`: that directory is left root-owned by the
  // dockerised CI run, so a local run dies in the reporter writing
  // `.last-run.json` — before reporting a single result. The visual config
  // already sidesteps this the same way.
  outputDir: "./behaviour-results",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8100",
    trace: "on",
    screenshot: "on",
    launchOptions: { slowMo: 300 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
