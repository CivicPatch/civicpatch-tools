import { personIdIn } from "../../people/person-cards.ts";

export const PERSON_FIELDS = {
  // `post_id` and `membership_label` are an office pick; for an existing person they travel
  // as `offices`, not in the patch (see `toPatchItem`).
  single: ["name", "post_id", "membership_label", "image", "cdn_image", "start_date", "end_date", "updated_at"],
  array:  ["other_names", "phones", "emails", "urls", "source_urls"],
};

// `id` is tracked so re-identifying a person (linking to an existing record)
// marks the row dirty and gets submitted, even with no other edits.
export const TRACKED_FIELDS = ["id", ...PERSON_FIELDS.single, ...PERSON_FIELDS.array];

// Which fields a person has had edited, as field keys. Derived on read from
// (current, baseline) rather than stamped onto the record, so it cannot go stale.
export function changedFieldKeys(person, original) {
  return TRACKED_FIELDS.filter(
    field => JSON.stringify(person[field]) !== JSON.stringify(original?.[field])
  );
}

// Rows can change without any field changing: a reorder, or a merge collapsing
// two rows into one. Both show up in the id sequence. Only ids the two lists
// share are compared — an added row has no baseline and is not a reorder.
export function listChanged(currentPeople, originalPeople) {
  const currentIds = currentPeople.map(p => p.id);
  const originalIds = originalPeople.map(p => p.id);
  const originalIdSet = new Set(originalIds);
  const shared = new Set(currentIds.filter(id => originalIdSet.has(id)));
  if (shared.size !== originalIds.length) return true;
  const currentOrder = currentIds.filter(id => shared.has(id));
  const originalOrder = originalIds.filter(id => shared.has(id));
  return currentOrder.join("|") !== originalOrder.join("|");
}

// Ids stop naming a person when a merge collapses two rows into one.
// A stale entry is not inert: `removedIds` is read when building the publish
// payload, so an id that later belongs to someone else drops them silently.
// Returns the same Set when nothing was stale, so callers can skip the update.
export function pruneIds(ids, livingIds) {
  const living = livingIds instanceof Set ? livingIds : new Set(livingIds);
  const kept = [...ids].filter((id) => living.has(personIdIn(id)));
  return kept.length === ids.size ? ids : new Set(kept);
}

// Build the publish payload: one patch item per person still on the list. Existing rows send
// only their changed fields; new or re-identified rows (id changed) send the whole entry, and
// so does a merge survivor, since the server diffs it against the merged person, not its baseline.
// The backend keys by id — a known id overlays the fields, an unknown id inserts the whole
// entry. Removal is not absence: `rosterEditPayload` says it as `offices: []`. A row removed
// by person id drops out here (a review says they are not on the roster at all); a roster row
// removed in one body does not, because their name correction still stands.
export function buildPeoplePatch(currentPeople, changesById, removedIds, survivorIds) {
  return currentPeople
    .filter(p => !removedIds.has(p.id))
    .map(p => survivorIds.has(p.id) ? survivorPatchItem(p) : toPatchItem(p, changesById.get(p.id)));
}

// An existing person's office pick travels as `offices` (roster-edit-payload.ts), not as a
// person field. A brand-new person still needs `post_id` in their patch: `officeEditsIn` only
// answers for somebody who already holds something.
const OFFICE_ONLY_FIELDS = ["post_id", "membership_label"];

function toPatchItem(person, changes) {
  const { _selected, _isNew, ...entry } = person;
  if (_isNew || changes.includes("id")) {
    return { id: entry.id, fields: entry };
  }
  const fields = {};
  for (const field of changes) {
    if (OFFICE_ONLY_FIELDS.includes(field)) continue;
    fields[field] = entry[field];
  }
  return { id: entry.id, fields };
}

function survivorPatchItem(person) {
  const { _selected, _isNew, ...entry } = person;
  const fields = {};
  for (const field of TRACKED_FIELDS) {
    if (field === "id" || OFFICE_ONLY_FIELDS.includes(field) || !(field in entry)) continue;
    fields[field] = entry[field];
  }
  return { id: entry.id, fields };
}
