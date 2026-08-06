// Which row of a rail takes the caret when a view opens on a field.
//
// The caller names a field, but the rail decides what is on screen — the two
// derive their visible sets separately — so a field the rail is not showing
// falls back to the first row rather than focusing nothing.

import { type FieldSpec } from "../review/field-model.js";

// Takes the key alone, not the whole FieldFocus: the ref that comes with it is
// the caller's business, not this rule's.
export function focusedKey(
  fields: FieldSpec[],
  focus: { key: string } | null,
): string | null {
  if (!focus) return null;
  const asked = fields.find((field) => field.key === focus.key);
  return (asked ?? fields[0])?.key ?? null;
}
