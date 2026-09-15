// Split out of field-controls.ts so civ-office-picker (which field-controls.ts mounts) can
// use these without a circular import: field-controls -> office-picker -> field-controls.
import { nothing } from "lit-html";
import { ref } from "lit-html/directives/ref.js";

export const inputValue = (e: Event) =>
  (e.target as HTMLInputElement | HTMLSelectElement).value;

// A callback ref, not a `Ref` object: only the template that renders a control
// knows when it exists, and the call is that signal.
export type FocusRef = (el?: Element) => void;

// Which field asked for focus, and the ref that takes it. The editor decides
// which row it lands on; the control decides which of its elements holds it.
export interface FieldFocus {
  key: string;
  attach: FocusRef;
}

// `nothing` in an element position is a no-op, so a control that was not asked
// for gets no ref at all.
export const attachFocus = (focusRef: FocusRef | null) =>
  focusRef ? ref(focusRef) : nothing;
