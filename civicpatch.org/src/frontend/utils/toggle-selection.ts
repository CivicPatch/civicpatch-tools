export function toggleSelection<T extends string>(selected: T[], value: T): T[] {
  return selected.includes(value)
    ? selected.filter((each) => each !== value)
    : [...selected, value];
}
