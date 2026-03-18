# civicpatch — Frontend Context

See project [AI_CONTEXT.md](../../AI_CONTEXT.md) for shared coding standards.

## Stack

Vanilla JS web components served by FastAPI.

- **Framework:** Haunted (React-like hooks) + `lit-html`
- **Bundler:** Rollup — `npm run build` (or `npm start` to watch)
- **Entry:** `src/frontend/` — components in `components/`, Jinja2 templates in `templates/`

## API calls

- All API calls live in `src/frontend/api.js` — no `fetch` calls in components or pages
- All exported functions are `async` — no `.then()` chains
- Functions return the parsed JSON directly and throw on non-ok responses

## Styles

- Global styles (tokens, theme, base element overrides, buttons, layout, utilities) live in `css/styles.css`
- Component styles live co-located with their JS: `components/<name>/<name>.css` or `pages/<page>/<name>.css`; `@import`ed at the bottom of `styles.css`
- No inline styles; no styles defined outside of `css/` or the component's own folder
- Use Pico CSS variables (`--pico-*`) for colors, spacing, and typography — never hardcode hex values except where Pico has no equivalent
- Color palette is Catppuccin — always use `--pico-*` variables for colors; override them with Catppuccin values at the `:root` level in `styles.css` as needed, never use `--catppuccin-*` variables directly in component rules
- BEM-style class names scoped to the component: `.pr-card__header`, `.pr-card__merge-button`
- Shared button variants share a base rule via grouped selector, then override per variant
- Button size variants: `.btn-sm` (compact monospace); destructive actions: `button.destructive`

## Events

- Child components communicate upward via `CustomEvent` with `bubbles: true`
- Event names are kebab-case on the wire (`state-change`, `selected-pull-request`), camelCase as handler props (`onMerge`, `onClose`)
- The page-level component owns all async state and API calls; children only dispatch events

## Local API testing

The API (`api.civicpatch.org`) runs at `http://localhost:8001` in development (set in `assets/env.js`).

Authenticate with `SERVICE_API_KEY` passed as the raw `Authorization` header value (no `Bearer` prefix):

```sh
curl -s -H "Authorization: $SERVICE_API_KEY" \
  "http://localhost:8001/api/v1/pull_requests?jurisdiction_ocdid=ocd-division/country:us/state:tx/place:austin"
```

Use it to inspect request/response shapes when debugging frontend API calls.

The civicpatch FastAPI server at `localhost:8000` proxies `/api/api_proxy/{path}` → `localhost:8001/api/v1/{path}`. Frontend `api.js` calls go directly to `localhost:8001` (via `API_URL` in `env.js`).

## Component conventions

- Custom elements are registered with `useShadowDOM: false`
- Shared components live in `components/`; page-specific ones live under `pages/<page-name>/`
- Reusable selection widgets (e.g. `civ-select-state`) belong in `components/` and are imported by pages that need them
