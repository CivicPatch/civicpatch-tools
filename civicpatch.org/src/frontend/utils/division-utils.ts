// Logic that has to stay in sync with the Python backend, not domain modeling of its own —
// same reasoning as ../components/username-utils.ts. Nothing enforces the sync; a drift here
// is silent.

// Mirrors `_DIVISION_LABELS` in `membership_label.py`; a drift shows the same division two
// ways on one screen.
export const DIVISION_LABELS: Record<string, string> = {
  ward: "Ward",
  council_district: "District",
  district: "District",
  precinct: "Precinct",
  subdistrict: "Subdistrict",
};

// Mirrors `_CARDINALS` in `label_parser.py`.
const CARDINALS = [
  "north",
  "south",
  "east",
  "west",
  "northeast",
  "northwest",
  "southeast",
  "southwest",
  "central",
] as const;

/** Mirrors `_is_value` in `label_parser.py`, and must stay the *same* closed set: a post whose
 * ocdid a scrape can never produce sits unverified forever with a duplicate beside it. */
export function isDivisionValue(value: string): boolean {
  const key = value.trim().toLowerCase();
  if (!key) return false;
  // Ordinals too: the parser normalises "3rd" to "3" before this test.
  if (/^\d+(st|nd|rd|th)?$/.test(key)) return true;
  if ((CARDINALS as readonly string[]).includes(key)) return true;
  return key.length === 1 && /[a-z]/.test(key);
}
