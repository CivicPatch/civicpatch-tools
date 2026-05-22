import { test as base } from "@playwright/test";
import { seedE2eFixtures, teardownE2eFixtures } from "./db.js";
import { createTestSession, injectSessionCookies, cleanupTestSession } from "./auth.js";

const TEST_USER = {
  provider: "github",
  provider_user_id: "test-user-e2e",
  email: "e2e@civicpatch.org",
  // Must match db.js's seeded role on this user.
  role: "contributors",
};

export const test = base.extend({
  // Seeds DB fixtures once per test and tears down after
  dbFixtures: [
    async ({}, use) => {
      await seedE2eFixtures();
      await use();
      await teardownE2eFixtures();
    },
    { auto: true },
  ],

  // Injects session cookies so tests start authenticated
  authenticatedPage: async ({ page, context, dbFixtures }, use) => {
    const baseUrl = process.env.BASE_URL ?? "http://localhost:8001";
    const { token, csrfNonce } = await createTestSession(
      TEST_USER.provider,
      TEST_USER.provider_user_id,
      TEST_USER.email,
      TEST_USER.role
    );
    await injectSessionCookies(context, token, csrfNonce, baseUrl);

    // Pre-set the state selector in localStorage so the review queue
    // filters to the seeded state without requiring URL params.
    await page.addInitScript(() => {
      localStorage.setItem("app:default-state", JSON.stringify({ __value: "nj", __expiresAt: null }));
    });

    // Expose csrfNonce so tests can include it in POST request headers
    page.csrfNonce = csrfNonce;
    await use(page);

    await cleanupTestSession(TEST_USER.provider, TEST_USER.provider_user_id);
  },
});

export { expect } from "@playwright/test";
