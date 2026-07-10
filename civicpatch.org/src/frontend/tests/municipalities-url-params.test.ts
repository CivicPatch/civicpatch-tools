import { describe, it, expect } from 'vitest';
import {
  parseMunicipalitiesParams,
  buildMunicipalitiesSearch,
} from '../pages/municipalities-page/url-params.js';

describe('parseMunicipalitiesParams', () => {
  it('returns all defaults for an empty query string', () => {
    expect(parseMunicipalitiesParams('')).toEqual({
      q: '',
      status: 'all',
      needsReview: false,
      sortKey: 'name',
      sortDir: 'asc',
      page: 1,
    });
  });

  it('parses every param when present', () => {
    expect(
      parseMunicipalitiesParams('?q=seattle&status=gap&needs_review=true&sort=officials&dir=desc&page=3'),
    ).toEqual({
      q: 'seattle',
      status: 'gap',
      needsReview: true,
      sortKey: 'officials',
      sortDir: 'desc',
      page: 3,
    });
  });

  it('falls back to defaults for an invalid status', () => {
    expect(parseMunicipalitiesParams('?status=bogus').status).toBe('all');
  });

  it('falls back to defaults for an invalid sort key', () => {
    expect(parseMunicipalitiesParams('?sort=bogus').sortKey).toBe('name');
  });

  it('falls back to page 1 for a non-numeric or non-positive page', () => {
    expect(parseMunicipalitiesParams('?page=abc').page).toBe(1);
    expect(parseMunicipalitiesParams('?page=0').page).toBe(1);
    expect(parseMunicipalitiesParams('?page=-5').page).toBe(1);
  });

  it('treats any dir value other than desc as asc', () => {
    expect(parseMunicipalitiesParams('?dir=bogus').sortDir).toBe('asc');
  });
});

describe('buildMunicipalitiesSearch', () => {
  it('produces an empty string when everything is default', () => {
    expect(
      buildMunicipalitiesSearch({
        q: '',
        status: 'all',
        needsReview: false,
        sortKey: 'name',
        sortDir: 'asc',
        page: 1,
      }),
    ).toBe('');
  });

  it('only includes params that differ from defaults', () => {
    expect(
      buildMunicipalitiesSearch({
        q: '',
        status: 'gap',
        needsReview: false,
        sortKey: 'name',
        sortDir: 'asc',
        page: 1,
      }),
    ).toBe('?status=gap');
  });

  it('round-trips a fully custom set of params', () => {
    const params = {
      q: 'seattle',
      status: 'gap',
      needsReview: true,
      sortKey: 'officials' as const,
      sortDir: 'desc' as const,
      page: 3,
    };
    expect(parseMunicipalitiesParams(buildMunicipalitiesSearch(params))).toEqual(params);
  });
});
