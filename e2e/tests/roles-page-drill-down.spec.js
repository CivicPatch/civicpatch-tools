/**
 * User story: a maintainer browses roles by level and state
 *
 * Given I open /roles
 * When I pick a level and type a state
 * Then the page asks for that level and state, and the select keeps showing my choice
 * And focus stays on the control I used, even while the roles reload
 * But if a load fails, the controls stay so I can try another
 *
 * `GET /api/v1/roles` is stubbed, so this covers the client wiring, not the response's shape:
 * tests/integration/routers/test_roles.py holds that against the real endpoint.
 */

import { test, expect } from "../fixtures/index.js";

const ROLES_ENDPOINT = "**/api/v1/roles*";
const ROLE = { id: "member", label: "Member", is_unique: false, aliases: [] };

const stubRoles = (page, requests) =>
  page.route(ROLES_ENDPOINT, (route) => {
    requests.push(route.request().url());
    return route.fulfill({ json: { data: { roles: [ROLE] } } });
  });

test("a chosen level and state are asked for, and the select keeps showing the level", async ({
  maintainerPage: page,
}) => {
  const requests = [];
  await stubRoles(page, requests);
  await page.goto("/roles");

  const level = page.getByLabel("Level");
  await level.focus();
  await level.selectOption("counties");
  await expect(level).toHaveValue("counties");
  await expect(level).toBeFocused();

  const state = page.getByLabel("State");
  await state.fill("vt");
  await state.press("Tab");

  await expect
    .poll(() => requests.at(-1))
    .toContain("/api/v1/roles?level=counties&state=vt");
  await expect(level).toHaveValue("counties");
});

test("a failed load keeps the controls", async ({ maintainerPage: page }) => {
  const requests = [];
  await stubRoles(page, requests);
  await page.goto("/roles");
  await expect(page.getByRole("cell", { name: "Member", exact: true })).toBeVisible();

  await page.unroute(ROLES_ENDPOINT);
  await page.route(ROLES_ENDPOINT, (route) => route.fulfill({ status: 500, json: {} }));
  await page.getByLabel("Level").selectOption("local");

  await expect(page.getByText("HTTP 500")).toBeVisible();
  await expect(page.getByLabel("Level")).toHaveValue("local");
});
