// Which states the page is looking at. Pure, and its own module so vitest can exercise the
// states without a DOM — a shadowed const in the mockup killed the whole script once and only
// surfaced by testing the states rather than the render.

// **Empty means everything.** The page opens on every state rather than an empty shell, so
// there is no "nothing selected" view to design and no first-run emptiness to explain.
export const isShown = (picked: string[], state: string) =>
  picked.length === 0 || picked.includes(state);

export const toggle = (picked: string[], state: string) =>
  picked.includes(state) ? picked.filter((s) => s !== state) : [...picked, state];

// `all` and `none` render the same rows, since an empty selection already means everything.
// What separates them is what happens next — after `all`, unpicking one state leaves 49.
export const hasPickedEverything = (picked: string[], total: number) =>
  picked.length === total;
