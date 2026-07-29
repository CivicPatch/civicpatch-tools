export const PERSON_FIELDS = {
  single: ["name", "image", "cdn_image", "start_date", "end_date", "updated_at"],
  array:  ["other_names", "phones", "emails", "urls", "source_urls"],
  object: ["office"],
};

// `id` is tracked so re-identifying a person (linking to an existing record)
// marks the row dirty and gets submitted, even with no other edits.
export const TRACKED_FIELDS = ["id", ...PERSON_FIELDS.single, ...PERSON_FIELDS.array, ...PERSON_FIELDS.object];

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

  const allOfficeNameParts = all
    .flatMap(p => (p.office?.name || "").split(" - ").map(s => s.trim()))
    .filter(Boolean);
  const dedupedOfficeNames = Array.from(new Set(allOfficeNameParts));
  if (dedupedOfficeNames.length > 0) {
    merged.office = { ...(merged.office || {}), name: dedupedOfficeNames.join(" - ") };
  }

  return { ...merged, _selected: false };
}

export function collapseInto(survivor, absorbed, list) {
  const merged = mergeFields(survivor, [absorbed]);
  return list.filter(p => p.id !== survivor.id && p.id !== absorbed.id).concat(merged);
}

// Build the publish payload: one patch item per non-deleted person. Existing rows send
// only their changed fields; new or re-identified rows (id changed) send the whole entry.
// The backend keys by id — a known id overlays the fields, an unknown id inserts the whole
// entry, and a base person absent from the list is a deletion. Deleted rows are omitted here.
export function buildPeoplePatch(currentPeople, changesById, deletedIds) {
  return currentPeople
    .filter(p => !deletedIds.has(p.id))
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
