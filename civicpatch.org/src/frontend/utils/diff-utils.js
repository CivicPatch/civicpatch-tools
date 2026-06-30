// The kind of change a diff entry represents — the contract between
// computePeopleDiff and its consumers (people-diff, diff-panel, data-panel).
export const DiffType = Object.freeze({
  ADDED: "added",
  REMOVED: "removed",
  CHANGED: "changed",
  UNCHANGED: "unchanged",
});

/**
 * Computes a people diff between two arrays keyed by person id.
 *
 * @param {Array} existing
 * @param {Array} proposed
 * @param {(existing: object, proposed: object) => boolean} isChanged
 * @returns {{ diffEntries: Array, unchangedEntries: Array }}
 */
export function computePeopleDiff(existing, proposed, isChanged) {
  const existingMap = Object.fromEntries((existing ?? []).map((p) => [p?.id, p]));
  const prMap = Object.fromEntries((proposed ?? []).map((p) => [p?.id, p]));
  const allKeys = Array.from(new Set([...Object.keys(existingMap), ...Object.keys(prMap)]));

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

  return { diffEntries, unchangedEntries };
}
