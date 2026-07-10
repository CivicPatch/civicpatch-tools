import { describe, it, expect } from 'vitest';
import {
  STATUS_FILTER_ALL,
  filterMunicipalities,
  sortMunicipalities,
  computeStatusPillCounts,
  countNeedsReview,
} from '../pages/municipalities-page/municipalities-filter.js';

const MUNICIPALITIES = [
  { jurisdiction_ocdid: 'a', name: 'Bellevue', status: 'fresh', officials_count: 5, last_verified_at: '2026-04-01T00:00:00Z', needs_review: false },
  { jurisdiction_ocdid: 'b', name: 'Aurora', status: 'stale', officials_count: 2, last_verified_at: '2026-01-01T00:00:00Z', needs_review: true },
  { jurisdiction_ocdid: 'c', name: 'Cascade', status: 'gap', officials_count: 0, last_verified_at: null, needs_review: false },
  { jurisdiction_ocdid: 'd', name: 'Denver', status: 'untracked', officials_count: 0, last_verified_at: null, needs_review: false },
];

describe('filterMunicipalities', () => {
  it('returns everything when query is empty and status is all', () => {
    const result = filterMunicipalities(MUNICIPALITIES, {
      query: '',
      status: STATUS_FILTER_ALL,
      needsReviewOnly: false,
    });
    expect(result).toHaveLength(4);
  });

  it('filters by name substring, case-insensitively', () => {
    const result = filterMunicipalities(MUNICIPALITIES, {
      query: 'ur',
      status: STATUS_FILTER_ALL,
      needsReviewOnly: false,
    });
    expect(result.map((m) => m.name)).toEqual(['Aurora']);
  });

  it('filters by exact status', () => {
    const result = filterMunicipalities(MUNICIPALITIES, {
      query: '',
      status: 'gap',
      needsReviewOnly: false,
    });
    expect(result.map((m) => m.name)).toEqual(['Cascade']);
  });

  it('filters by needsReviewOnly, independent of status', () => {
    const result = filterMunicipalities(MUNICIPALITIES, {
      query: '',
      status: STATUS_FILTER_ALL,
      needsReviewOnly: true,
    });
    expect(result.map((m) => m.name)).toEqual(['Aurora']);
  });

  it('composes query, status, and needsReviewOnly with AND', () => {
    const result = filterMunicipalities(MUNICIPALITIES, {
      query: 'aurora',
      status: 'stale',
      needsReviewOnly: true,
    });
    expect(result.map((m) => m.name)).toEqual(['Aurora']);

    const noMatch = filterMunicipalities(MUNICIPALITIES, {
      query: 'aurora',
      status: 'fresh',
      needsReviewOnly: true,
    });
    expect(noMatch).toEqual([]);
  });
});

describe('sortMunicipalities', () => {
  it('sorts by name ascending', () => {
    const result = sortMunicipalities(MUNICIPALITIES, { key: 'name', dir: 'asc' });
    expect(result.map((m) => m.name)).toEqual(['Aurora', 'Bellevue', 'Cascade', 'Denver']);
  });

  it('sorts by name descending', () => {
    const result = sortMunicipalities(MUNICIPALITIES, { key: 'name', dir: 'desc' });
    expect(result.map((m) => m.name)).toEqual(['Denver', 'Cascade', 'Bellevue', 'Aurora']);
  });

  it('sorts by officials count ascending', () => {
    const result = sortMunicipalities(MUNICIPALITIES, { key: 'officials', dir: 'asc' });
    expect(result.map((m) => m.officials_count)).toEqual([0, 0, 2, 5]);
  });

  it('sorts by last_verified_at, nulls first ascending', () => {
    const result = sortMunicipalities(MUNICIPALITIES, { key: 'last_verified', dir: 'asc' });
    expect(result.map((m) => m.name)).toEqual(['Cascade', 'Denver', 'Aurora', 'Bellevue']);
  });

  it('does not mutate the input array', () => {
    const copy = [...MUNICIPALITIES];
    sortMunicipalities(MUNICIPALITIES, { key: 'name', dir: 'asc' });
    expect(MUNICIPALITIES).toEqual(copy);
  });
});

describe('computeStatusPillCounts', () => {
  it('counts each status plus an all total', () => {
    expect(computeStatusPillCounts(MUNICIPALITIES)).toEqual({
      all: 4,
      fresh: 1,
      stale: 1,
      gap: 1,
      untracked: 1,
    });
  });

  it('returns all zero counts for an empty list', () => {
    expect(computeStatusPillCounts([])).toEqual({
      all: 0,
      fresh: 0,
      stale: 0,
      gap: 0,
      untracked: 0,
    });
  });
});

describe('countNeedsReview', () => {
  it('counts only rows flagged needs_review, regardless of status', () => {
    expect(countNeedsReview(MUNICIPALITIES)).toBe(1);
  });

  it('returns zero when nothing needs review', () => {
    expect(countNeedsReview(MUNICIPALITIES.filter((m) => !m.needs_review))).toBe(0);
  });
});
