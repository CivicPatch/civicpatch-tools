// Who last stood behind a field's value, for the editor's per-field tag.

export interface PersonAssertion {
  field_path: string;
  kind: string;
  value: unknown;
  created_at: string;
  created_by_name: string | null;
}

export const ACCEPT = "accept";

const UNNAMED = "someone";

/** The accepts on each field, newest first, per person.
 *
 * Rejects are left out: they explain an *absence*, so there is no value on screen to tag.
 */
export function acceptsByField(
  assertions: PersonAssertion[],
): Map<string, PersonAssertion[]> {
  const byField = new Map<string, PersonAssertion[]>();
  for (const assertion of assertions) {
    if (assertion.kind !== ACCEPT) continue;
    byField.set(assertion.field_path, [
      ...(byField.get(assertion.field_path) ?? []),
      assertion,
    ]);
  }
  return byField;
}

export function provenanceLabel(
  accepts: PersonAssertion[] | undefined,
): string | null {
  if (!accepts?.length) return null;
  const newest = accepts.reduce((latest, next) =>
    next.created_at > latest.created_at ? next : latest,
  );
  const on = new Date(newest.created_at);
  const when = Number.isNaN(on.getTime())
    ? null
    : on.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
  const who = newest.created_by_name || UNNAMED;
  return when ? `Published by ${who}, ${when}` : `Published by ${who}`;
}

// ── the lock ─────────────────────────────────────────────────────────────────

export const LOCK_HELD = "held";
export const LOCK_OVERRODE = "overrode";

export interface FieldLock {
  state: typeof LOCK_HELD | typeof LOCK_OVERRODE;
  /** Who published it, always — this is what the provenance line used to say. */
  label: string;
  /** What the source said, when an assertion changed it. Null when it agrees. */
  disclosure: string | null;
}

const asList = (value: unknown): string[] =>
  value == null ? [] : Array.isArray(value) ? value.map(String) : [String(value)];

/** What the lock hides, in the reviewer's words.
 *
 * Two sentences, because the data distinguishes two acts: an accept that replaced what was
 * scraped, and a reject that removed one of several values. A reject is the more useful of the
 * two — the value is gone from the field, so this is the only place it still exists on screen.
 */
function disclose(sourceValue: unknown, publishedValue: unknown): string | null {
  const source = asList(sourceValue);
  const published = new Set(asList(publishedValue));
  const removed = source.filter((value) => !published.has(value));
  if (!removed.length) return null;
  return removed.length === source.length && published.size
    ? `Source said ${removed.join(", ")}`
    : `Removed ${removed.join(", ")}`;
}

/** The lock on one field, or null where nobody has stood behind it.
 *
 * `sourceValue` is `undefined` for a field no assertion moved — most fields on most people,
 * since only a field someone actually edited carries a claim at all.
 */
export function fieldLock(
  accepts: PersonAssertion[] | undefined,
  sourceValue: unknown,
  publishedValue: unknown,
): FieldLock | null {
  const label = provenanceLabel(accepts);
  if (!label) return null;
  if (sourceValue === undefined) return { state: LOCK_HELD, label, disclosure: null };
  return {
    state: LOCK_OVERRODE,
    label,
    disclosure: disclose(sourceValue, publishedValue),
  };
}
