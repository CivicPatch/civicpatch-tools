# civicpatch.org frontend

See root `AGENTS.md` for shared coding standards.

## Naming

- **JavaScript** — `camelCase` for variables, functions, and hooks; `kebab-case` for file names; `snake_case` for object keys on data objects (API responses, data passed between components)
- **CSS** — `kebab-case` for class names (BEM)

## Components

- New frontend components must be written in TypeScript (`.ts`) — do not create new `.js` component files
- When importing a `.ts` component from a `.js` file, use the `.ts` extension explicitly (e.g. `import "../foo/foo.ts"`). Rollup does not resolve `.js` → `.ts` for plain JS importers; the `.js` → `.ts` remapping only works within TypeScript files.
- After any change to a frontend component, run `mise run typecheck-fe` and fix all errors before considering the task done

## Component events (lit-html + haunted)

A child component talks to its parent by **dispatching a `CustomEvent` from its own element (`host`)**; the parent listens with `@event`. Use named handlers — no callback props.

Dispatch through `hostDispatch(host, name, detail?)` from `utils/host-dispatch.ts`. It exists because six modal components had each grown the same private wrapper: the `{ bubbles: true, composed: true }` options repeat on every event, and a component emitting `saved` and `cancel` writes them twice. Taking `host` as the first argument is what keeps the rule below intact — the helper cannot be called on the click target by accident.

```ts
// child: event name is a module constant (no magic string); emit from host
// (the element the parent listens on) via a named handler
const CANCEL_EVENT = "cancel";
const handleCancel = () => hostDispatch(host, CANCEL_EVENT);
html`<button @click=${handleCancel}>Cancel</button>`;

// parent: the @event name must be a literal here (lit-html parses the template)
html`<civ-thing @cancel=${() => ...}></civ-thing>`;
```

- Dispatch from `host`, not from the click event's target — the parent listens on the component element, and a component's own events should originate there.
- Only give a handler an `(e)` parameter when it needs the incoming DOM event itself (`e.preventDefault()`, `e.stopPropagation()`, `e.target.value`).
- The no-magic-strings rule has one known exception here: lit-html `@event` bindings need a literal event name in the template (it is parsed, not evaluated), so the listener side stays literal even when the emitter uses a constant

## CSS Style

- One property per line, each on its own indented line — no inlining multiple
  properties on the same line. Readability over compactness.
- Group conceptually related rules with lightweight section comments
  (`/* Header */`, `/* Field rows */`).
- One blank line between rule blocks, no extra vertical whitespace.
