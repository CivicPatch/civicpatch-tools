/**
 * Build a map of person names to their other_names (identities)
 */
export function buildIdentitiesMap(people) {
  if (!people) return {};
  
  return people.reduce((acc, person) => {
    if (acc[person.name]) {
      acc[person.name] = [...new Set([...acc[person.name], ...(person.other_names || [])])];
    } else {
      acc[person.name] = [...new Set(person.other_names || [])];
    }
    return acc;
  }, {});
}
