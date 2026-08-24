// Who last stood behind a field's value, for the editor's per-field tag.

export interface PersonAssertion {
  field_path: string;
  kind: string;
  value: unknown;
  asserted_at: string;
  asserted_by_name: string | null;
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
    next.asserted_at > latest.asserted_at ? next : latest,
  );
  const on = new Date(newest.asserted_at);
  const when = Number.isNaN(on.getTime())
    ? null
    : on.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
  const who = newest.asserted_by_name || UNNAMED;
  return when ? `Published by ${who}, ${when}` : `Published by ${who}`;
}
