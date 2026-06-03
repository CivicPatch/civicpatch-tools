// Pure list-reorder helpers — each returns a new array, never mutates the input.

export function moveUp<T>(order: T[], index: number): T[] {
  if (index <= 0) return order;
  const next = [...order];
  const above = next[index - 1];
  next[index - 1] = next[index];
  next[index] = above;
  return next;
}

export function moveDown<T>(order: T[], index: number): T[] {
  if (index < 0 || index >= order.length - 1) return order;
  const next = [...order];
  const below = next[index + 1];
  next[index + 1] = next[index];
  next[index] = below;
  return next;
}

export function moveToTop<T>(order: T[], index: number): T[] {
  if (index <= 0) return order;
  const next = [...order];
  const [item] = next.splice(index, 1);
  next.unshift(item);
  return next;
}

export function applyDrop<T>(order: T[], fromIndex: number, toIndex: number): T[] {
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return order;
  const next = [...order];
  const [item] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, item);
  return next;
}
