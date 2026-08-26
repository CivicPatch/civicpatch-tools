/** Which fields the scrape diff compares, and how to read one off a person.
 *
 * Split from the component so it can be tested without the haunted runtime, matching
 * `posts-model` and `field-model`.
 *
 * Every key is a plain field. `labels` and `division_ocdid` replaced `office.name` and
 * `office.division_ocdid` — the only dotted paths, and the only reason this ever walked one.
 * `office.name` was `labels` joined with " - " upstream, so a person sighted on three pages
 * that each spelled their office differently read back as three offices.
 */

import { divisionOcdidToFriendly } from "../ocdid-utils.js";

export type DiffField = { key: string; label: string };

export const FIELDS: DiffField[] = [
  { key: "name", label: "Name" },
  { key: "labels", label: "Post" },
  { key: "division_ocdid", label: "Division" },
  { key: "phones", label: "Phones" },
  { key: "emails", label: "Emails" },
  { key: "urls", label: "URLs" },
  { key: "start_date", label: "Start Date" },
  { key: "end_date", label: "End Date" },
  { key: "image", label: "Image" },
];

export function getFieldValue(
  person: Record<string, unknown> | undefined | null,
  key: string,
): string {
  const val = person?.[key];
  if (Array.isArray(val)) return val.join(", ");
  return (val as string) ?? "";
}

export function displayValue(key: string, raw: string): string {
  if (key === "division_ocdid") return divisionOcdidToFriendly(raw) || raw || "—";
  return raw || "—";
}

function normalizeForCompare(val: string): string {
  return val.toLowerCase().trim();
}

export function changedFields(
  existing: Record<string, unknown> | undefined | null,
  proposed: Record<string, unknown> | undefined | null,
): DiffField[] {
  return FIELDS.filter(
    ({ key }) =>
      normalizeForCompare(getFieldValue(existing, key)) !==
      normalizeForCompare(getFieldValue(proposed, key)),
  );
}


/** Does the scrape say something different about where this person serves?
 *
 * The post-and-division half of `changedFields`, which the review card summarises on its own.
 * Shared so the card's count and the panel's rows cannot disagree about what changed.
 */
export function postChanged(
  existing: Record<string, unknown> | undefined | null,
  proposed: Record<string, unknown> | undefined | null,
): boolean {
  return (["labels", "division_ocdid"] as const).some(
    (key) => getFieldValue(existing, key) !== getFieldValue(proposed, key),
  );
}
