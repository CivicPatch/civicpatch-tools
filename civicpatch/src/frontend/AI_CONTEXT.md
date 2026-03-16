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

- All styles go in `src/frontend/css/styles.css` — no inline styles, no per-component CSS files
- Use Pico CSS variables (`--pico-*`) for colors, spacing, and typography — never hardcode hex values except where Pico has no equivalent
- Color palette is Catppuccin — always use `--pico-*` variables for colors; override them with Catppuccin values at the `:root` level in `styles.css` as needed, never use `--catppuccin-*` variables directly in component rules
- BEM-style class names scoped to the component: `.pr-card__header`, `.pr-card__merge-button`
- Shared button variants share a base rule via grouped selector, then override per variant
- Button size variants: `.btn-sm` (compact monospace); destructive actions: `button.destructive`

## Events

- Child components communicate upward via `CustomEvent` with `bubbles: true`
- Event names are kebab-case on the wire (`state-change`, `selected-pull-request`), camelCase as handler props (`onMerge`, `onClose`)
- The page-level component owns all async state and API calls; children only dispatch events

## Component conventions

- Custom elements are registered with `useShadowDOM: false`
- Shared components live in `components/`; page-specific ones live under `pages/<page-name>/`
- Reusable selection widgets (e.g. `civ-select-state`) belong in `components/` and are imported by pages that need them
