import { describe, it, expect } from 'vitest';
import { formatDuration } from '../utils/duration-utils.js';

describe('formatDuration', () => {
  it('returns an em dash for null/undefined', () => {
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(undefined)).toBe('—');
  });

  it('formats sub-minute durations in seconds', () => {
    expect(formatDuration(45)).toBe('45s');
  });

  it('formats exact minutes without a seconds remainder', () => {
    expect(formatDuration(120)).toBe('2m');
  });

  it('formats minutes with a seconds remainder', () => {
    expect(formatDuration(125)).toBe('2m 5s');
  });
});
