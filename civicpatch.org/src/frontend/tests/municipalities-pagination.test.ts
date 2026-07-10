import { describe, it, expect } from 'vitest';
import { paginate, computePageWindow } from '../pages/municipalities-page/pagination.js';

const ITEMS = Array.from({ length: 45 }, (_, i) => i + 1);

describe('paginate', () => {
  it('slices the first page', () => {
    const result = paginate(ITEMS, 1, 20);
    expect(result.pageItems).toEqual(ITEMS.slice(0, 20));
    expect(result.start).toBe(1);
    expect(result.end).toBe(20);
    expect(result.total).toBe(45);
    expect(result.totalPages).toBe(3);
  });

  it('slices a middle page', () => {
    const result = paginate(ITEMS, 2, 20);
    expect(result.pageItems).toEqual(ITEMS.slice(20, 40));
    expect(result.start).toBe(21);
    expect(result.end).toBe(40);
  });

  it('slices a partial last page', () => {
    const result = paginate(ITEMS, 3, 20);
    expect(result.pageItems).toEqual(ITEMS.slice(40, 45));
    expect(result.start).toBe(41);
    expect(result.end).toBe(45);
  });

  it('clamps a page number beyond the last page to the last page', () => {
    const result = paginate(ITEMS, 99, 20);
    expect(result.pageItems).toEqual(ITEMS.slice(40, 45));
    expect(result.end).toBe(45);
  });

  it('clamps a page number below 1 to page 1', () => {
    const result = paginate(ITEMS, 0, 20);
    expect(result.pageItems).toEqual(ITEMS.slice(0, 20));
  });

  it('handles an empty list without dividing by zero', () => {
    const result = paginate([], 1, 20);
    expect(result.pageItems).toEqual([]);
    expect(result.start).toBe(0);
    expect(result.end).toBe(0);
    expect(result.total).toBe(0);
    expect(result.totalPages).toBe(1);
  });
});

describe('computePageWindow', () => {
  it('returns every page when there are 7 or fewer total (nothing to collapse)', () => {
    expect(computePageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(computePageWindow(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it('shows the first two, an ellipsis, and the last two when on page 1', () => {
    expect(computePageWindow(1, 10)).toEqual([1, 2, 'ellipsis', 9, 10]);
  });

  it('shows both ellipses with a window around a middle page', () => {
    expect(computePageWindow(5, 10)).toEqual([1, 2, 'ellipsis', 4, 5, 6, 'ellipsis', 9, 10]);
  });

  it('shows the first two, an ellipsis, and the last two when on the last page', () => {
    expect(computePageWindow(10, 10)).toEqual([1, 2, 'ellipsis', 9, 10]);
  });

  it('omits the leading ellipsis once the window reaches page 3', () => {
    // window = [2,3,4], adjacent to the [1,2] boundary — no gap, no ellipsis needed
    expect(computePageWindow(3, 10)).toEqual([1, 2, 3, 4, 'ellipsis', 9, 10]);
  });
});
