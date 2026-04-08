/**
 * Sorts an array of people keys by their original order, then by division string (using semantic/natural compare) if present.
 * @param {Array<string>} keys - The array of keys to sort.
 * @param {Object} originalOrderMap - Map of key -> original index.
 * @param {Object} dataMap - Map of key -> person object (from either existing or pr data).
 * @returns {Array<string>} Sorted array of keys.
 */
export const sortPeopleKeys = (keys, originalOrderMap, dataMap) => {
  return [...keys].sort((a, b) => {
    // First, sort by original order
    const idxA = originalOrderMap[a] ?? Infinity;
    const idxB = originalOrderMap[b] ?? Infinity;
    if (idxA !== idxB) return idxA - idxB;

    // If original order is the same, sort by division string using localeCompare with numeric option
    const divA = dataMap[a]?.office?.division_ocdid || '';
    const divB = dataMap[b]?.office?.division_ocdid || '';
    return divA.localeCompare(divB, undefined, { numeric: true, sensitivity: 'base' });
  });
}