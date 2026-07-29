// People-editing helpers shared by the full editor (<civ-editable-people-list>)
// and the review session card, so both add and resolve people identically.

import { batchResolvePeople } from "../../api.js";
import { jurisdictionToDivisionBase } from "./person-edit-utils.ts";

const INTERNAL_FIELDS = ["_isNew", "_selected"];

// A fully-empty new person — only the default division is pre-filled (the
// jurisdiction base). Both the review card and the full editor want
// this clean slate; required fields then flag until the reviewer fills them.
export function emptyPerson(personId, jurisdictionOcdid) {
  return {
    id: personId,
    _selected: false,
    _isNew: true,
    name: "",
    other_names: [],
    phones: [],
    emails: [],
    urls: [],
    start_date: null,
    end_date: null,
    office: {
      name: "",
      division_ocdid: jurisdictionOcdid ? jurisdictionToDivisionBase(jurisdictionOcdid) : null,
    },
    image: null,
    cdn_image: null,
    jurisdiction_ocdid: jurisdictionOcdid,
    source_urls: [],
    updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
  };
}

// Resolve proposed people against existing records: returns the same people
// tagged with `_isNew` (no match found) plus a map of id -> match result.
export async function resolvePeopleMatches(jurisdictionOcdid, people) {
  const clean = people.map((person) => {
    const copy = { ...person };
    for (const field of INTERNAL_FIELDS) delete copy[field];
    return copy;
  });
  const resolved = await batchResolvePeople(jurisdictionOcdid, clean);
  const matchMap = {};
  const tagged = people.map((person, i) => {
    const match = resolved.data[i];
    matchMap[person.id] = match;
    return { ...person, _isNew: !match?.person };
  });
  return { tagged, matchMap };
}
