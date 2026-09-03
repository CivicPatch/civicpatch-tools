/**
 * Visual regression baselines.
 *
 * The behaviour suite in ../tests asserts what the app *does*; it would stay
 * green through a completely broken restyle. This asserts what the app *looks
 * like*, so that removing Pico can be verified rather than eyeballed.
 *
 * It is not a test of correctness — a diff here means "something moved", and
 * whether that is a bug or the point is for the reader to say. During the Pico
 * removal the answer is always "bug": every step is supposed to change nothing.
 *
 * Run:     mise run visual
 * Accept:  mise run visual-update   (only when a change is intended)
 */

import { test, expect } from "../fixtures/index.js";
import { SCALE_CHANGESET_ID, READ_ONLY_CHANGESET_ID } from "../fixtures/db.js";

const THEMES = ["light", "dark"];

// useLocalStorage wraps values; the theme is stored with no expiry, so the
// navbar reads it back as a plain string on first paint.
const themeEntry = (theme) =>
  JSON.stringify({ __value: theme, __expiresAt: null });

// Every page a reviewer or maintainer can land on. Blog and login are included
// because styles.css spends 511 lines on them — they are the most Pico-exposed
// surfaces in the app and the easiest to regress unnoticed.
const PAGES = [
  { name: "home", path: "/" },
  { name: "login", path: "/login" },
  { name: "queue", path: "/queue" },
  { name: "review-landing", path: "/review?state=nj" },
  // One page since the view tabs went: the roster, then Preview as a section under it.
  {
    name: "review-session",
    path: `/review/session?changeset_id=${SCALE_CHANGESET_ID}`,
  },
  {
    name: "review-read-only",
    path: `/review/session?changeset_id=${READ_ONLY_CHANGESET_ID}`,
  },
  // The person-edit modal. Like the config editor it only exists after a click,
  // and several UX changes target it — without this capture they are unverifiable.
  {
    name: "review-modal",
    path: `/review/session?changeset_id=${SCALE_CHANGESET_ID}`,
    open: async (page) => {
      await page.locator(".review-row__open").first().click();
      await page.locator("dialog[open]").waitFor();
    },
  },
  { name: "issues", path: "/issues", role: "admin" },
  // The config editor is a modal, so it needs a click to exist. It is the only
  // place config-editor.css renders, and that file carries the largest cluster
  // of Pico accordion overrides — an unopened baseline would leave them
  // unverified.
  {
    name: "issues-config-editor",
    path: "/issues",
    role: "admin",
    open: async (page) => {
      await page.getByRole("button", { name: "Resolve" }).first().click();
      // Wait on the dialog, not the host: <issues-config-editor> wraps a
      // <civ-modal> and has no layout box of its own, so a visibility check on
      // the host can never pass.
      await page.locator("dialog[open]").waitFor();
    },
  },
  { name: "activity", path: "/activity/changelogs" },
  // Maintainer, so the capture includes the scrape control the page carries; a default-role
  // reader sees the same page without it.
  {
    name: "changesets",
    path: "/activity/changesets",
    role: "maintainer",
  },
  { name: "settings", path: "/settings" },
  { name: "roles", path: "/roles", role: "maintainer" },
  { name: "municipalities", path: "/nj/local" },
  // The jurisdiction detail page is the catch-all route, reached by folder form.
  // It is the largest surface the baseline was missing, and the only place
  // edit-people renders.
  {
    name: "jurisdiction",
    path: "/nj/local/place_e2e_test",
    role: "maintainer",
  },
  { name: "blog-list", path: "/blog" },
  // Interaction states, which no page capture reaches on its own. Forced rather
  // than driven through a real submit — the point is to put the CSS states on
  // screen, and a failing OTP round-trip would make the baseline depend on the
  // error text.
  {
    name: "login-disabled-state",
    path: "/login",
    open: async (page) => {
      await page.locator(".email-login__form input").first().waitFor();
      await page.evaluate(() => {
        for (const el of document.querySelectorAll(
          ".email-login__form input, .email-login__form button",
        )) {
          el.disabled = true;
        }
      });
    },
  },
];

// Pages gated above `contributors` need a matching identity, or they render the
// Unauthorized page and the baseline records nothing about the page itself.
// Regions that legitimately differ between runs. Masked rather than excluded so
// the surrounding layout is still compared.
const VOLATILE = [
  ".streak-graph", // keyed on today's date
  "[data-visual-volatile]",
];

// Wait until nothing has mutated the DOM for `quietMs`.
//
// `networkidle` is not enough. useAuth renders once with every permission false
// and re-renders when /api/permissions resolves, so the nav gains links and the
// whole page reflows — screenshot in that window and the baseline is a coin
// flip. A quiet period is the general form of that wait: it covers permissions,
// late data, and anything else that paints twice, without the spec having to
// know which endpoint each page calls.
async function waitForDomQuiet(page, quietMs = 400, timeoutMs = 15_000) {
  await page.evaluate(
    ([quietMs, timeoutMs]) =>
      new Promise((resolve, reject) => {
        let timer;
        const observer = new MutationObserver(() => {
          clearTimeout(timer);
          timer = setTimeout(finish, quietMs);
        });
        function finish() {
          observer.disconnect();
          clearTimeout(giveUp);
          resolve();
        }
        const giveUp = setTimeout(() => {
          observer.disconnect();
          reject(new Error(`DOM still mutating after ${timeoutMs}ms`));
        }, timeoutMs);
        observer.observe(document.documentElement, {
          subtree: true,
          childList: true,
          attributes: true,
          characterData: true,
        });
        timer = setTimeout(finish, quietMs);
      }),
    [quietMs, timeoutMs],
  );
}

// Font Awesome arrives via a CDN kit *script*, which injects its CSS and only
// then loads the font files. `document.fonts.ready` can resolve before any of
// that starts, so a slow CDN produces a page with every icon missing — which is
// a tens-of-thousands-of-pixels difference, not a subtle one. Wait for the face
// to actually be usable, and fail loudly rather than screenshot a page whose
// icons never arrived.
async function waitForIconFont(page) {
  await page.waitForFunction(
    () =>
      [...document.fonts].some(
        (f) => /Font Awesome/i.test(f.family) && f.status === "loaded",
      ),
    undefined,
    { timeout: 20_000 },
  );
}

async function settle(page) {
  // Webfonts change every metric on the page. Without this the first run after a
  // cold cache renders in the fallback face and every baseline is wrong.
  await page.evaluate(() => document.fonts.ready);
  await waitForIconFont(page);
  await page.waitForLoadState("networkidle");
  await waitForDomQuiet(page);
}

// Playwright reads the fixtures a test needs from the literal destructuring in
// its callback, so the three roles are spelled out rather than looked up.
async function capture(page, { name, path, theme, open }) {
  await page.addInitScript(
    ([key, value]) => localStorage.setItem(key, value),
    ["app:theme", themeEntry(theme)],
  );
  await page.goto(path);

  // The inline script in base.html applies the theme before first paint, so
  // this is both the theme gate and the "document is up" gate.
  await expect
    .poll(() => page.evaluate(() => document.documentElement.dataset.theme))
    .toBe(theme);

  await settle(page);
  if (open) {
    await open(page);
    await settle(page);
  }

  await expect(page).toHaveScreenshot(`${name}-${theme}.png`, {
    fullPage: true,
    animations: "disabled",
    caret: "hide",
    mask: VOLATILE.map((selector) => page.locator(selector)),
  });
}

const forRole = (role) =>
  PAGES.filter((p) => (p.role ?? "contributor") === role);

for (const theme of THEMES) {
  test.describe(`visual — ${theme}`, () => {
    for (const entry of forRole("contributor")) {
      test(entry.name, async ({ authenticatedPage: page }) => {
        await capture(page, { ...entry, theme });
      });
    }

    for (const entry of forRole("maintainer")) {
      test(entry.name, async ({ maintainerPage: page }) => {
        await capture(page, { ...entry, theme });
      });
    }

    for (const entry of forRole("admin")) {
      test(entry.name, async ({ adminPage: page }) => {
        await capture(page, { ...entry, theme });
      });
    }
  });
}
