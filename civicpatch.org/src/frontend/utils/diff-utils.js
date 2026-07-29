// The kind of change a diff entry represents — the contract between
// computePeopleDiff and its consumers (people-diff, diff-panel, data-panel).
export const DiffType = Object.freeze({
  ADDED: "added",
  REMOVED: "removed",
  CHANGED: "changed",
  UNCHANGED: "unchanged",
});

// Ids that appear more than once in a list. `Object.fromEntries` keeps the last
// entry per key, so a duplicate id means one person silently vanishes from the
// diff — not added, not changed, not removed — and publish then sends a single
// record while the other entry's data is lost without ever having been shown.
//
// This is reachable today (two scraped people sharing a name or an alias), and
// merge makes it the steady state: matching consults aliases, so the next scrape
// resolves both entries of a merged pair to the survivor's id. resolve_people_ids
// detects ambiguity only in the other direction — one scraped person matching
// several existing records.
//
// The collapse itself is kept, because everything downstream is keyed by person
// id: the frozen field set, expansion, deletions and restorations would all be
// ambiguous with two entries sharing one key. What changes is that it is now
// reported rather than silent.
function duplicateIdsIn(people) {
  const seen = new Set();
  const duplicates = new Set();
  for (const person of people ?? []) {
    const id = person?.id;
    if (id === undefined) continue;
    if (seen.has(id)) duplicates.add(id);
    else seen.add(id);
  }
  return duplicates;
}

/**
 * Computes a people diff between two arrays keyed by person id.
 *
 * @param {Array} existing
 * @param {Array} proposed
 * @param {(existing: object, proposed: object) => boolean} isChanged
 * @returns {{ diffEntries: Array, unchangedEntries: Array, duplicateIds: string[] }}
 */
export function computePeopleDiff(existing, proposed, isChanged) {
  const existingMap = Object.fromEntries((existing ?? []).map((p) => [p?.id, p]));
  const prMap = Object.fromEntries((proposed ?? []).map((p) => [p?.id, p]));
  const allKeys = Array.from(new Set([...Object.keys(existingMap), ...Object.keys(prMap)]));
  const duplicateIds = [
    ...new Set([...duplicateIdsIn(existing), ...duplicateIdsIn(proposed)]),
  ];

  const diffEntries = [];
  const unchangedEntries = [];

  for (const key of allKeys) {
    const e = existingMap[key];
    const p = prMap[key];
    if (!e)
      diffEntries.push({ type: DiffType.ADDED, person: p, from: null });
    else if (!p)
      diffEntries.push({ type: DiffType.REMOVED, person: e, from: e });
    else if (isChanged(e, p))
      diffEntries.push({ type: DiffType.CHANGED, person: p, from: e });
    else
      unchangedEntries.push({ type: DiffType.UNCHANGED, person: p, from: e });
  }

  return { diffEntries, unchangedEntries, duplicateIds };
}
