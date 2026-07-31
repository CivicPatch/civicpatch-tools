export const divisionOcdidToFriendly = (division_ocdid) => {
  if (!division_ocdid) return "";

  const parts = division_ocdid.split("/");
  const lastPart = parts[parts.length - 1];

  let [label, value] = ["", ""];

  try {
    [label, value] = lastPart.split(":");
  } catch (error) {
    console.error("Error parsing division_ocdid:", error);
    return "";
  }

  switch (label) {
    case "council_district":
      return `[D${value}]`;
    case "ward":
      return `[W${value}]`;
    case "place":
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

export const jurisdictionOcdidToState = jurisdiction_ocdid => {
  if (!jurisdiction_ocdid) return "";
  return jurisdiction_ocdid.split("/")[2]?.split(":")[1] ?? "";
};

// Inverse of backend folder_to_jurisdiction_ocdid (shared/utils/id_utils.py).
// Assumes /government output_type → "local" (only other entry in data.yml
// is "meetings", which doesn't reach the homepage flow).
export const jurisdictionOcdidToPath = jurisdiction_ocdid => {
  if (!jurisdiction_ocdid) return "";
  const parts = jurisdiction_ocdid.split("/");
  if (parts.length < 5) return "";

  const state = jurisdictionOcdidToState(jurisdiction_ocdid);
  if (!state) return "";

  const middle = parts.slice(3, -1);
  if (middle.length === 0) return "";

  const segments = [];
  for (const seg of middle) {
    const [label, name] = seg.split(":");
    if (!label || !name) return "";
    segments.push(label === "county" ? `county_${name}` : `${label}_${name}`);
  }

  return `${state}/local/${segments.join("__")}`;
};