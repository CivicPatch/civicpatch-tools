import {
  DIVISION_COUNCIL_DISTRICT,
  DIVISION_WARD,
  PLACE_LABEL,
} from "./edit-people/person-edit-utils.ts";

/** The last segment of a division ocdid, split into its designation and value.
 *
 * "ocd-division/country:us/state:wa/place:x/ward:3" -> { key: "ward", value: "3" }
 *
 * One place, because renderers disagree about presentation but not about parsing:
 * `divisionOcdidToFriendly` wants a compact badge, `divisionName` a row heading.
 */
export const parseDivision = (division_ocdid) => {
  const tail = division_ocdid?.split("/").pop() ?? "";
  const [key = "", value = ""] = tail.split(":");
  return { key, value };
};

export const divisionOcdidToFriendly = (division_ocdid) => {
  if (!division_ocdid) return "";

  const { key: label, value } = parseDivision(division_ocdid);

  switch (label) {
    case DIVISION_COUNCIL_DISTRICT:
      return `[D${value}]`;
    case DIVISION_WARD:
      return `[W${value}]`;
    case PLACE_LABEL:
      return "";
    default:
      return `${label} ${value}`
  }
}

const toTitleCaseMap = (str) => {
  return str.toLowerCase().split(' ').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
}

export const jurisdictionOcdidToFriendly = jurisdiction_ocdid => {
  if (!jurisdiction_ocdid) return "";
  const parts = jurisdiction_ocdid.split("/");
  const last = parts[parts.length - 2];
  let [_placeLabel, placeValue] = last ? last.split(":") : ["", ""];

  placeValue = placeValue.replace(/_/g, ' ');

  return toTitleCaseMap(placeValue) || jurisdiction_ocdid;
};

// Every jurisdiction ocdid starts with this. Mirrors OCDID_PREFIX in shared/utils/id_utils.py.
export const OCDID_PREFIX = "ocd-jurisdiction";

/** An ocdid's segments, or null when the string is not one.
 *
 * One place, for the same reason `parseDivision` is one place: the readers below disagree
 * about what to pull out, not about what a jurisdiction ocdid looks like, and each was
 * re-deriving "is this even one" on its way past.
 *
 * Five segments is the shortest real ocdid — prefix / country / state / place / government.
 */
const jurisdictionSegments = (jurisdiction_ocdid) => {
  if (!jurisdiction_ocdid?.startsWith(`${OCDID_PREFIX}/`)) return null;
  const parts = jurisdiction_ocdid.split("/");
  return parts.length < 5 ? null : parts;
};

// The two-letter state code an ocdid belongs to, e.g. "me". Callers building a
// review-session url need this on its own, without the rest of the path.
export const jurisdictionOcdidToState = jurisdiction_ocdid =>
  jurisdictionSegments(jurisdiction_ocdid)?.[2]?.split(":")[1] ?? "";

// A jurisdiction page's URL is its ocdid. `encodeURI`, not `encodeURIComponent`: the slashes
// and colons are legal in a path and stay readable, and only what must be escaped is — two
// place names carry an "ñ".
//
// This used to reimplement `jurisdiction_ocdid_to_folder` in JavaScript, one of two encoders
// that had to agree across languages. Using the identifier as the URL deletes that problem.
export const jurisdictionOcdidToPath = jurisdiction_ocdid =>
  // Validated, not just encoded. The folder encoder this replaced returned "" for anything
  // malformed, and callers rely on that to render nothing rather than a broken link —
  // `encodeURI` alone would happily hand back "garbage".
  jurisdictionSegments(jurisdiction_ocdid) ? encodeURI(jurisdiction_ocdid) : "";