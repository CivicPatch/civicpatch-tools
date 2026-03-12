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