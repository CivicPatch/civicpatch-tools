export const PERSON_FIELDS = {
  // `post_id` is the post a reviewer picked. A scalar like any other here, so a merge takes
  // the first non-empty and a survivor with no pick inherits one instead of losing it.
  single: ["name", "post_id", "image", "cdn_image", "start_date", "end_date", "updated_at"],
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

export function mergeFields(survivor, absorbed) {
  const all = [survivor, ...absorbed];
  const merged = { ...survivor };

  for (const field of PERSON_FIELDS.single) {
    const firstNonEmpty = all.map(p => p[field]).find(v => v != null && v !== "");
    merged[field] = firstNonEmpty ?? null;
  }

  for (const field of PERSON_FIELDS.array) {
    merged[field] = Array.from(new Set(
      all.flatMap(p => (p[field] || []).filter(Boolean))
    ));
  }

  const absorbedNames = absorbed.map(p => p.name).filter(Boolean);
  merged.other_names = Array.from(new Set([...merged.other_names, ...absorbedNames]))
    .filter(n => n !== merged.name);

  return { ...merged, _selected: false };
}

// Ids stop naming a person when a merge collapses two rows into one.
// A stale entry is not inert: `removedIds` is read when building the publish
// payload, so an id that later belongs to someone else drops them silently.
// Returns the same Set when nothing was stale, so callers can skip the update.
export function pruneIds(ids, livingIds) {
  const living = livingIds instanceof Set ? livingIds : new Set(livingIds);
  const kept = [...ids].filter((id) => living.has(id));
  return kept.length === ids.size ? ids : new Set(kept);
}

// Build the publish payload: one patch item per non-deleted person. Existing rows send
// only their changed fields; new or re-identified rows (id changed) send the whole entry.
// The backend keys by id — a known id overlays the fields, an unknown id inserts the whole
// entry, and a base person absent from the list is a deletion. Deleted rows are omitted here.
export function buildPeoplePatch(currentPeople, changesById, removedIds) {
  return currentPeople
    .filter(p => !removedIds.has(p.id))
    .map(p => toPatchItem(p, changesById.get(p.id)));
}

function toPatchItem(person, changes) {
  const { _selected, _isNew, ...entry } = person;
  if (_isNew || changes.includes("id")) {
    return { id: entry.id, fields: entry };
  }
  const fields = {};
  for (const field of changes) {
    fields[field] = entry[field];
  }
  return { id: entry.id, fields };
}
