# Frontend

Server-rendered Jinja pages that mount web components. No SPA, no router, no
client-side navigation — each page is a normal document that boots one component.

**Stack:** [lit-html](https://lit.dev/docs/libraries/standalone-templates/) for
templates, [haunted](https://github.com/matthewp/haunted) for hooks
(`useState`/`useEffect` against custom elements), [Vite](https://vite.dev/) for
bundling, [Pico CSS](https://picocss.com/) as the base layer. Vitest for unit
tests, Playwright (in `/e2e`) for end-to-end.

See the repo root `CLAUDE.md` for coding standards and `civicpatch.org/CLAUDE.md`
for backend context.

---

## How a page works

Five links in the chain. Every page follows it; there are no exceptions.

```
1. Backend route          routers/frontend.py renders a template
2. Jinja template         templates/pages/review-session.html
                            ├─ vite_asset('assets/review-session.ts')  → <script>
                            ├─ vite_css('assets/review-session.ts')    → <link>
                            └─ <review-session-page></review-session-page>
3. Vite entry point       assets/review-session.ts
                            ├─ import "../components/navbar.js"
                            └─ import "../pages/review-session-page/index.js"
4. Page component         pages/review-session-page/index.js
                            customElements.define("review-session-page", …)
5. The element upgrades and renders.
```

**Custom elements register as an import side effect.** If nothing imports the
module, the tag never upgrades — it renders as an inert unknown element with no
content and collapses to zero height, with no console error. A blank section of
a page is almost always a missing import.

Entry points are declared in `vite.config.js` (`rollupOptions.input`) — there are
12, one per page. Adding a page means adding a file to `assets/`, an entry in
`vite.config.js`, a template in `templates/pages/`, and a route in
`routers/frontend.py`.

---

## Where things go

```
assets/          Vite entry points. Two imports each: navbar + the page. Nothing else.
pages/           One directory per page: <name>-page/. index.ts defines <name>-page.
components/      Reusable across pages.
  basic/         Generic primitives with no domain knowledge (modal, table, chip).
  review/        The review card model + field schema. Shared by all review views.
  …
hooks/           Haunted hooks. One hook per file, named use-*.ts.
utils/           Pure functions. No DOM, no fetch, no lit-html.
css/             Global layers — see "Styling".
templates/       Jinja. layouts/base.html + one file per page in pages/.
tests/           Vitest unit tests for pure logic.
vite.py          Jinja helpers that resolve hashed asset paths from the manifest.
```

The rule: **`pages/` for something one page uses, `components/` for something two
or more use, `utils/` for anything with no DOM involvement.** A component that
grows a `.css` file, a test, or helper modules earns a directory; a single
self-contained file can stay flat.

Known drift, do not copy: `components/ocdid-utils.js` and `components/job-status.js`
belong in `utils/` (they are a pure function and an enum). Several components sit
flat in `components/` while equivalents have directories.

---

## The review area

Eight directories carry "review" in the name. They are not variations on one
thing — this is the map:

| directory | what it is |
|---|---|
| `components/review/` | **The shared model.** `review-cards.ts` (one card per person), `field-model.ts` (`FIELD_SCHEMA`, the collapse rule), `field-controls.ts`, `merge-model.ts`. Pure. Every view below reads from it. |
| `components/review-overview/` | **Overview tab** — triage a whole card at a glance. One list in seat order; untouched people fold to a compact row. |
| `components/person-editor/` | **Detail tab** — the editor. `person-editor-list` → `person-editor` → `editor-field`, one field per row as `label │ control │ was … Restore`. Also mounted by the review modal and the jurisdiction page. |
| `components/review-preview/` | **Preview tab** — the published result, *not* a diff. Deliberately carries no diff vocabulary: no state colours, no strikethrough, no attention icons. |
| `components/review-checklist/` | The complete index of a card's issues. |
| `pages/review-page/` | The review **landing** page — pick a jurisdiction, see stats. |
| `pages/review-session-page/` | The review **session** — owns the card under review, the tab bar, and the frozen-field set the three views must agree on. |
| `components/review-panel/` | **Legacy (v1).** `civ-review-table` + `civ-diff-panel`, used by the jurisdiction page and PR cards. Superseded by the person editor; still live, do not extend. |

The three tabs share the **card model** but each owns its own presentation. When
changing what a card *means*, change `components/review/`; when changing how one
tab *looks*, change that tab.

`components/diff-panel/` and `components/edit-people/review-table.js` are also
part of the v1 tier.

---

## Component conventions

**Custom element** for anything with state, lifecycle, or a tag in a template:

```ts
// child: event name is a module constant; emit from host via a named handler
const CANCEL_EVENT = "cancel";
const handleCancel = () =>
  host.dispatchEvent(new CustomEvent(CANCEL_EVENT, { bubbles: true, composed: true }));

customElements.define("civ-thing", component(Thing, { useShadowDOM: false }));
```

**Plain render function** for pure presentation with no state — returns a
template, called as `${renderThing(props)}`:

```ts
export function renderPersonFace(card: ReviewCard, onPick: (id: string) => void) {
  return html`<button class="review-face" @click=${() => onPick(card.personId)}>…</button>`;
}
```

Both patterns are in use and both are fine — pick by whether it needs state.
Shadow DOM is off everywhere (`useShadowDOM: false`) so global CSS applies.

**Naming:** new elements get a `civ-` prefix when reusable across pages, and a
bare name when page-scoped (`review-session-page`, `issues-config-editor`).
Existing tags are split roughly evenly and are not worth retagging.

**New components are TypeScript.** When importing a `.ts` component from a `.js`
file, write the `.ts` extension explicitly (`import "../foo/foo.ts"`) — Rollup
does not remap `.js` → `.ts` for plain-JS importers.

**Events over callbacks across module boundaries;** callback props are used
within a page's own component tree. See the root `CLAUDE.md` events section.

---

## Styling

```
css/tokens.css     Design tokens. Start here.
css/styles.css     Global layout, shared classes.
css/elements.css   Bare-element defaults.
css/blog.css       Blog-only.
```

Component CSS lives next to the component (`badge/badge.css`) and is imported by
it (`import "./badge.css"`). Do not inline `<style>` blocks in templates.

- **Reference tokens, not literals** — `var(--text-sm)`, not `0.75rem`.
- **BEM**, kebab-case, block name matching the component.
- One property per line.
- New tokens get plain names (`--page-width`). The `--civ-*` namespace is legacy;
  don't extend it.
- Class names built by interpolation (`` class="review-row--${status}" ``) are
  invisible to grep — check the browser before deleting CSS that looks unused.

---

## Working on it

```sh
mise run dev              # app + vite dev server on :8004
mise run typecheck-fe     # required after any component change
mise run tcp              # tests
```

**`typecheck-fe` currently proves less than it looks like it does** — `tsconfig.json`
has `strict: false` and `checkJs: false`, and excludes `tests/`. Treat a pass as
a syntax check, not a correctness guarantee.

Unit tests in `tests/` cover pure logic — the card model, field model, diff
utils, URL params. Rendering and interaction are covered by Playwright in
`/e2e`. Much of the older tier (`components/edit-people/`, `components/basic/`,
`pages/issues-page/`, `pages/queue-page/`, `pages/jurisdictions-page/`) has no
unit tests; add them with the first change you make there.

### Gotchas

- **Rebuilding the frontend is not enough for e2e.** `vite.py` caches the
  manifest with `@lru_cache` at startup, so the backend keeps serving the old
  hashed filenames until the container restarts. Symptom: a 404 on the JS bundle
  and a blank page that looks exactly like a code regression. Rebuild *and*
  restart `civicpatch-org-e2e`.
- **A new npm dependency needs installing inside the dev container too.**
  `docker-compose.yml` mounts your source over `/app` but declares
  `/app/node_modules` as an anonymous volume, so the container keeps its own
  dependencies and an `npm install` on the host never reaches the dev server.
  Symptom: Vite cannot resolve the new import, serves the importing module with
  an empty MIME type, and the browser reports `NS_ERROR_CORRUPTED_CONTENT` plus
  a spray of CORS and `@vite/client` errors that have nothing to do with the
  cause. If the import is in something central like `navbar.js`, every page
  breaks at once. Fix:

      docker exec civicpatch-tools-api-frontend-1 npm install
      docker compose restart api-frontend

- **A blank region with no console error** usually means an unimported
  component — see "How a page works".
- **Comments must stand on their own.** Do not cite a spec, plan, or design doc,
  by path or by section number. If a rule is worth pointing at, write the rule
  into the comment.