import {
  DIVISION_COUNCIL_DISTRICT,
  DIVISION_WARD,
  PLACE_LABEL,
} from "./edit-people/person-edit-utils.ts";

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

export const OCDID_PREFIX = "ocd-jurisdiction";

const jurisdictionSegments = (jurisdiction_ocdid) => {
  if (!jurisdiction_ocdid?.startsWith(`${OCDID_PREFIX}/`)) return null;
  const parts = jurisdiction_ocdid.split("/");
  return parts.length < 5 ? null : parts;
};

export const jurisdictionOcdidToState = jurisdiction_ocdid =>
  jurisdictionSegments(jurisdiction_ocdid)?.[2]?.split(":")[1] ?? "";

const STATE_NAMES = {
  al: "Alabama", ak: "Alaska", az: "Arizona", ar: "Arkansas", ca: "California",
  co: "Colorado", ct: "Connecticut", de: "Delaware", dc: "District of Columbia",
  fl: "Florida", ga: "Georgia", hi: "Hawaii", id: "Idaho", il: "Illinois",
  in: "Indiana", ia: "Iowa", ks: "Kansas", ky: "Kentucky", la: "Louisiana",
  me: "Maine", md: "Maryland", ma: "Massachusetts", mi: "Michigan", mn: "Minnesota",
  ms: "Mississippi", mo: "Missouri", mt: "Montana", ne: "Nebraska", nv: "Nevada",
  nh: "New Hampshire", nj: "New Jersey", nm: "New Mexico", ny: "New York",
  nc: "North Carolina", nd: "North Dakota", oh: "Ohio", ok: "Oklahoma", or: "Oregon",
  pa: "Pennsylvania", ri: "Rhode Island", sc: "South Carolina", sd: "South Dakota",
  tn: "Tennessee", tx: "Texas", ut: "Utah", vt: "Vermont", va: "Virginia",
  wa: "Washington", wv: "West Virginia", wi: "Wisconsin", wy: "Wyoming",
  as: "American Samoa", gu: "Guam", mp: "Northern Mariana Islands",
  pr: "Puerto Rico", vi: "U.S. Virgin Islands",
};

export const stateNameForCode = (state_code) =>
  STATE_NAMES[state_code?.toLowerCase()] ?? "";

export const jurisdictionOcdidToPath = jurisdiction_ocdid =>
  jurisdictionSegments(jurisdiction_ocdid) ? encodeURI(jurisdiction_ocdid) : "";