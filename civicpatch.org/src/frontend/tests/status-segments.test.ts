import { describe, it, expect } from 'vitest';
import { computeStatusSegments, STATUS_ORDER } from '../components/progress-dashboard/status-segments.js';

describe('computeStatusSegments', () => {
  it('computes each status\'s percent of the total', () => {
    const result = computeStatusSegments({ fresh: 30, stale: 10, gap: 50, untracked: 10 });
    expect(result).toEqual([
      { key: 'fresh', count: 30, percent: 30 },
      { key: 'stale', count: 10, percent: 10 },
      { key: 'gap', count: 50, percent: 50 },
      { key: 'untracked', count: 10, percent: 10 },
    ]);
  });

  it('returns STATUS_ORDER keys in order', () => {
    const result = computeStatusSegments({ fresh: 1, stale: 1, gap: 1, untracked: 1 });
    expect(result.map((s) => s.key)).toEqual(STATUS_ORDER);
  });

  it('defaults missing keys to zero rather than throwing', () => {
    const result = computeStatusSegments({ fresh: 5 });
    expect(result).toEqual([
      { key: 'fresh', count: 5, percent: 100 },
      { key: 'stale', count: 0, percent: 0 },
      { key: 'gap', count: 0, percent: 0 },
      { key: 'untracked', count: 0, percent: 0 },
    ]);
  });

  it('returns zero percent for every status when the total is zero', () => {
    const result = computeStatusSegments({ fresh: 0, stale: 0, gap: 0, untracked: 0 });
    expect(result.every((s) => s.percent === 0)).toBe(true);
  });

  it('handles undefined input without throwing', () => {
    const result = computeStatusSegments(undefined);
    expect(result.every((s) => s.count === 0 && s.percent === 0)).toBe(true);
  });
});
