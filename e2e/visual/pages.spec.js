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
import { SCALE_REQUEST_ID, READ_ONLY_REQUEST_ID } from "../fixtures/db.js";

const THEMES = ["light", "dark"];

// useLocalStorage wraps values; the theme is stored with no expiry, so the
// navbar reads it back as a plain string on first paint.
const themeEntry = (theme) => JSON.stringify({ __value: theme, __expiresAt: null });

// Every page a reviewer or maintainer can land on. Blog and login are included
// because styles.css spends 511 lines on them — they are the most Pico-exposed
// surfaces in the app and the easiest to regress unnoticed.
const PAGES = [
  { name: "home", path: "/" },
  { name: "login", path: "/login" },
  { name: "queue", path: "/queue" },
  { name: "review-landing", path: "/review?state=nj" },
  { name: "review-overview", path: `/review/session?request_id=${SCALE_REQUEST_ID}&view=overview` },
  { name: "review-detail", path: `/review/session?request_id=${SCALE_REQUEST_ID}&view=detail` },
  { name: "review-preview", path: `/review/session?request_id=${SCALE_REQUEST_ID}&view=preview` },
  { name: "review-read-only", path: `/review/session?request_id=${READ_ONLY_REQUEST_ID}&view=detail` },
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
  { name: "activity", path: "/activity" },
  { name: "settings", path: "/settings" },
  { name: "roles", path: "/roles", role: "maintainer" },
  { name: "municipalities", path: "/nj/local" },
  { name: "blog-list", path: "/blog" },
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

async function settle(page) {
  // Webfonts change every metric on the page. Without this the first run after a
  // cold cache renders in the fallback face and every baseline is wrong.
  await page.evaluate(() => document.fonts.ready);
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

const forRole = (role) => PAGES.filter((p) => (p.role ?? "contributor") === role);

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
