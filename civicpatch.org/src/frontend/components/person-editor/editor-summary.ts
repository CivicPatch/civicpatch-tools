// What a card is asking of you, in one line.
//
// The status label named the state ("changed"); this names the *work* — how many
// fields moved and whether any of them needs a decision. That is what a reviewer
// scanning twenty people is actually looking for, so it replaces the label in the
// state header rather than sitting beside it.

import { isContextField, type Issue, type SurvivingField } from "../fields/field-model.js";
import { PersonStatus, type PersonStatusKey } from "../people/person-cards.js";

export interface EditorSummaryInput {
  status: PersonStatusKey;
  surviving: SurvivingField[];
  issues: Issue[];
  // Clear-on-edit: once the reviewer touches a card its issue markers are
  // presumed addressed. Errors are not cleared this way — they are recomputed
  // from the record, so a still-invalid field still counts.
  isDirty: boolean;
}

// A departure is one decision, not a field count. The banner in the card body
// explains it; this names it.
const DEPARTURE_SUMMARY: Partial<Record<PersonStatusKey, string>> = {
  [PersonStatus.REMOVED]: "Not found in this scrape",
  [PersonStatus.DELETED]: "You removed this person",
};

const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? "" : "s"}`;

// Context fields are always visible and are never a change, so counting them
// would report work on a card that has none.
function changedFieldCount(surviving: SurvivingField[]): number {
  return surviving.filter((entry) => entry.state !== "same" && !isContextField(entry.field)).length;
}

function attentionCount(input: EditorSummaryInput): number {
  const errors = input.surviving.filter((entry) => entry.error).length;
  return errors + (input.isDirty ? 0 : input.issues.length);
}

export function editorSummary(input: EditorSummaryInput): string {
  const departure = DEPARTURE_SUMMARY[input.status];
  if (departure) return departure;

  const parts: string[] = [];

  // A new person's fields are all "added" — saying "6 fields changed" describes
  // the diff rather than the person.
  if (input.status === PersonStatus.ADDED) {
    parts.push("New person");
  } else {
    const changed = changedFieldCount(input.surviving);
    if (changed) parts.push(`${plural(changed, "field")} changed`);
  }

  const attention = attentionCount(input);
  if (attention) parts.push(`${plural(attention, "thing")} to check`);

  if (!parts.length) return "No changes";
  return parts.join(", ");
}
