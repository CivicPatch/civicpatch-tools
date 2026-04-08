export function buildOtherNames(proposedPerson, existingPerson) {
  return Array.from(new Set([
    ...(proposedPerson.other_names || []),
    ...(existingPerson?.name ? [existingPerson.name] : []),
    ...(existingPerson?.other_names || []),
  ])).filter(n => n !== proposedPerson.name);
}
