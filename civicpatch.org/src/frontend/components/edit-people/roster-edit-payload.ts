// What the roster editor sends to `POST /api/v1/jurisdictions/roster-edits`: one entry per
// person, carrying the fields they changed and the whole set of posts that person should hold.
//
// Three sources become one list. A patch item is what `buildPeoplePatch` produced. An office
// change is an existing person's pick, diffed against the post they hold. A removed person is
// `offices: []`, which rejects every post they hold — the old patch dropped them and let the
// server infer removal from absence.

import type { OfficeEdit } from "../person-editor/office-edits.js";

// A brand-new person's pick rides in their fields, because `officeEditsIn` only answers for
// somebody who already holds something. These two are posts, not person fields.
const OFFICE_FIELDS = ["post_id", "membership_label"];

export interface OfficeEditPayload {
  id: string;
  membership_label: string | null;
}

export interface PersonEdit {
  id: string;
  fields?: Record<string, unknown>;
  offices?: OfficeEditPayload[];
}

interface PatchItem {
  id: string;
  fields: Record<string, unknown>;
}

function withoutOfficeFields(fields: Record<string, unknown>) {
  const kept = { ...fields };
  for (const field of OFFICE_FIELDS) delete kept[field];
  return kept;
}

function pickInFields(fields: Record<string, unknown>): OfficeEditPayload | null {
  const postId = fields.post_id;
  if (typeof postId !== "string" || !postId) return null;
  const label = fields.membership_label;
  return { id: postId, membership_label: typeof label === "string" ? label : null };
}

export function rosterEditPayload(
  patch: PatchItem[],
  officeEdits: OfficeEdit[],
  removedIds: Iterable<string>,
): PersonEdit[] {
  const byPerson = new Map<string, PersonEdit>();

  for (const item of patch) {
    const person: PersonEdit = { id: item.id, fields: withoutOfficeFields(item.fields) };
    const pick = pickInFields(item.fields);
    if (pick) person.offices = [pick];
    byPerson.set(item.id, person);
  }

  for (const change of officeEdits) {
    const person = byPerson.get(change.personId) ?? { id: change.personId };
    person.offices = [{ id: change.postId, membership_label: change.membershipLabel }];
    byPerson.set(change.personId, person);
  }

  for (const id of removedIds) {
    byPerson.set(id, { id, offices: [] });
  }

  return [...byPerson.values()];
}
