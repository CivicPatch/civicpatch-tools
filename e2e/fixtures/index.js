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

// Separate identity used by tests that need write access to role config
// (maintainers+). Auth resolves role from the session-cached value when there's
// no DB row, so the user doesn't need to be seeded.
const MAINTAINER_USER = {
  provider: "github",
  provider_user_id: "test-maintainer-e2e",
  email: "e2e-maintainer@civicpatch.org",
  role: "maintainers",
};

// Admin-only pages (/issues) need a third identity. Same trick as the
// maintainer: the role comes from the session-cached value, so no DB row.
const ADMIN_USER = {
  provider: "github",
  provider_user_id: "test-admin-e2e",
  email: "e2e-admin@civicpatch.org",
  role: "admins",
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
    // Only set if absent — tests that mutate app:default-state via the
    // navbar selector must not be clobbered on subsequent navigations.
    await page.addInitScript(() => {
      if (localStorage.getItem("app:default-state") === null) {
        localStorage.setItem("app:default-state", JSON.stringify({ __value: "nj", __expiresAt: null }));
      }
    });

    // Expose csrfNonce so tests can include it in POST request headers
    page.csrfNonce = csrfNonce;
    await use(page);

    await cleanupTestSession(TEST_USER.provider, TEST_USER.provider_user_id);
  },

  // Same as authenticatedPage but with a maintainers-role identity, for tests
  // that exercise role-config writes (gated at can_write_config = maintainers+).
  maintainerPage: async ({ page, context, dbFixtures }, use) => {
    const baseUrl = process.env.BASE_URL ?? "http://localhost:8001";
    const { token, csrfNonce } = await createTestSession(
      MAINTAINER_USER.provider,
      MAINTAINER_USER.provider_user_id,
      MAINTAINER_USER.email,
      MAINTAINER_USER.role,
    );
    await injectSessionCookies(context, token, csrfNonce, baseUrl);
    await page.addInitScript(() => {
      if (localStorage.getItem("app:default-state") === null) {
        localStorage.setItem("app:default-state", JSON.stringify({ __value: "nj", __expiresAt: null }));
      }
    });
    page.csrfNonce = csrfNonce;
    await use(page);
    await cleanupTestSession(MAINTAINER_USER.provider, MAINTAINER_USER.provider_user_id);
  },

  // Same again with an admins-role identity, for pages gated at can_view_issues_page.
  adminPage: async ({ page, context, dbFixtures }, use) => {
    const baseUrl = process.env.BASE_URL ?? "http://localhost:8001";
    const { token, csrfNonce } = await createTestSession(
      ADMIN_USER.provider,
      ADMIN_USER.provider_user_id,
      ADMIN_USER.email,
      ADMIN_USER.role,
    );
    await injectSessionCookies(context, token, csrfNonce, baseUrl);
    await page.addInitScript(() => {
      if (localStorage.getItem("app:default-state") === null) {
        localStorage.setItem("app:default-state", JSON.stringify({ __value: "nj", __expiresAt: null }));
      }
    });
    page.csrfNonce = csrfNonce;
    await use(page);
    await cleanupTestSession(ADMIN_USER.provider, ADMIN_USER.provider_user_id);
  },
});

export { expect } from "@playwright/test";
