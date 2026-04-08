export const PERSON_FIELDS = {
  single: ["name", "image", "cdn_image", "start_date", "end_date", "updated_at"],
  array:  ["other_names", "phones", "emails", "urls", "source_urls"],
  object: ["office"],
};

export const TRACKED_FIELDS = [...PERSON_FIELDS.single, ...PERSON_FIELDS.array, ...PERSON_FIELDS.object];

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
