// People-editing helpers shared by the full editor (<civ-editable-people-list>)
// and the review session card, so both add and resolve people identically.

import { batchResolvePeople } from "../../api.js";

const INTERNAL_FIELDS = ["_isNew", "_dirty", "_changes", "_selected", "_deleted"];

// A fresh, unsaved council member. Carries over the previous row's url/source so
// consecutive adds from the same page need less retyping.
export function blankPerson(personId, jurisdictionOcdid, people) {
  const last = people[people.length - 1] ?? null;
  return {
    id: personId,
    _changes: [],
    _selected: false,
    _deleted: false,
    _isNew: true,
    name: "",
    other_names: [],
    phones: [],
    emails: [],
    urls: last?.urls?.[0] ? [last.urls[0]] : [],
    start_date: null,
    end_date: null,
    office: {
      name: "Council Member",
      division_ocdid: people[0]?.office?.division_ocdid ?? null,
    },
    image: null,
    cdn_image: null,
    jurisdiction_ocdid: jurisdictionOcdid,
    source_urls: last?.source_urls?.[0] ? [last.source_urls[0]] : [],
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
