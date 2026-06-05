export const PERSON_FIELDS = {
  single: ["name", "image", "cdn_image", "start_date", "end_date", "updated_at"],
  array:  ["other_names", "phones", "emails", "urls", "source_urls"],
  object: ["office"],
};

// `id` is tracked so re-identifying a person (linking to an existing record)
// marks the row dirty and gets submitted, even with no other edits.
export const TRACKED_FIELDS = ["id", ...PERSON_FIELDS.single, ...PERSON_FIELDS.array, ...PERSON_FIELDS.object];

export function applyUpdate(person, updates, original) {
  const next = { ...person, ...updates };
  const changedFields = TRACKED_FIELDS.filter(
    field => JSON.stringify(next[field]) !== JSON.stringify(original?.[field])
  );
  return { ...next, _dirty: changedFields.length > 0 || updates._deleted === true, _changes: changedFields };
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

  return { ...merged, _dirty: true, _changes: TRACKED_FIELDS, _selected: false };
}

export function collapseInto(survivor, absorbed, list) {
  const merged = mergeFields(survivor, [absorbed]);
  return list.filter(p => p.id !== survivor.id && p.id !== absorbed.id).concat(merged);
}

// Build the publish payload: one patch item per non-deleted person. Existing rows send
// only their changed fields; new or re-identified rows (id changed) send the whole entry.
// The backend keys by id — a known id overlays the fields, an unknown id inserts the whole
// entry, and a base person absent from the list is a deletion. Deleted rows are omitted here.
export function buildPeoplePatch(currentPeople) {
  return currentPeople.filter(p => !p._deleted).map(toPatchItem);
}

function toPatchItem(person) {
  const { _dirty, _changes, _selected, _deleted, _isNew, ...entry } = person;
  const changes = _changes || [];
  if (_isNew || changes.includes("id")) {
    return { id: entry.id, fields: entry };
  }
  const fields = {};
  for (const field of changes) {
    fields[field] = entry[field];
  }
  return { id: entry.id, fields };
}
