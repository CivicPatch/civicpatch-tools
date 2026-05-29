/**
 * Happy-path coverage for the /roles page: add → exclude → include → remove cycle.
 *
 * Backend route integration tests pin each endpoint's behavior in isolation
 * (tests/integration/routers/test_jurisdictions_config.py); this spec verifies
 * the full UI ↔ backend wiring — button click → API call → UI re-renders
 * against the updated server state.
 *
 * Uses the State section because it's open by default and doesn't require
 * driving the locality autocomplete. Writes to the NJ state scope; the test
 * uses a sentinel role name and the afterEach hook cleans up any leftover row.
 */

import pg from "pg";
import { test, expect } from "../fixtures/index.js";

const SENTINEL_ROLE = "E2E Sentinel Role";

async function wipeSentinel() {
  const client = new pg.Client({
    connectionString:
      process.env.E2E_DB_URL ?? "postgres://e2e:e2e_password@localhost:8101/e2e_db",
  });
  await client.connect();
  await client.query("DELETE FROM role_terms WHERE value = $1", [SENTINEL_ROLE]);
  await client.end();
}

test.describe("Roles page edit cycle", () => {
  test.afterEach(async () => {
    await wipeSentinel();
  });

  test("add → exclude → include → remove", async ({ maintainerPage }) => {
    const page = maintainerPage;
    // Auto-accept all native confirm() dialogs that fire from
    // Exclude/Include/Remove buttons.
    page.on("dialog", (d) => d.accept());

    await page.goto("/roles");

    // The state section is open by default and labeled with the state code.
    const stateSection = page.locator(".config-editor__section").filter({
      has: page.locator(".config-editor__section-label", { hasText: "NJ" }),
    });
    await expect(stateSection).toBeVisible();

    // ── ADD ────────────────────────────────────────────────────────────
    // Wait for the Roles subsection to load (tables render only after fetch).
    await expect(stateSection.locator(".config-editor__subsection-label", { hasText: "Roles" })).toBeVisible();

    // Click "+ Add role" — the first add-btn in this section is the Roles one;
    // "+ Add exclusion" comes after.
    await stateSection.getByRole("button", { name: "+ Add role" }).click();

    // The civ-modal form has a single text input for "Role".
    await page.getByRole("dialog").getByRole("textbox").first().fill(SENTINEL_ROLE);
    await page.getByRole("dialog").getByRole("button", { name: "Add" }).click();

    // ── VERIFY APPEARS IN ROLES ────────────────────────────────────────
    const rolesTable = stateSection.locator("civ-term-table").nth(0);
    await expect(rolesTable.getByRole("cell", { name: SENTINEL_ROLE })).toBeVisible();

    // ── EXCLUDE ────────────────────────────────────────────────────────
    const sentinelRoleRow = rolesTable.locator("tr").filter({ hasText: SENTINEL_ROLE });
    await sentinelRoleRow.getByRole("button", { name: "Exclude" }).click();

    // ── VERIFY MOVED TO EXCLUSIONS ─────────────────────────────────────
    const exclusionsTable = stateSection.locator("civ-term-table").nth(1);
    await expect(exclusionsTable.getByRole("cell", { name: SENTINEL_ROLE })).toBeVisible();
    await expect(rolesTable.getByRole("cell", { name: SENTINEL_ROLE })).toHaveCount(0);

    // ── INCLUDE (BACK) ─────────────────────────────────────────────────
    const sentinelExclusionRow = exclusionsTable.locator("tr").filter({ hasText: SENTINEL_ROLE });
    await sentinelExclusionRow.getByRole("button", { name: "Include" }).click();

    await expect(rolesTable.getByRole("cell", { name: SENTINEL_ROLE })).toBeVisible();
    await expect(exclusionsTable.getByRole("cell", { name: SENTINEL_ROLE })).toHaveCount(0);

    // ── REMOVE ─────────────────────────────────────────────────────────
    await rolesTable.locator("tr").filter({ hasText: SENTINEL_ROLE })
      .getByRole("button", { name: "Remove" }).click();

    await expect(rolesTable.getByRole("cell", { name: SENTINEL_ROLE })).toHaveCount(0);
    await expect(exclusionsTable.getByRole("cell", { name: SENTINEL_ROLE })).toHaveCount(0);
  });
});
