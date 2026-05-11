import { describe, it, expect } from 'vitest';
import { buildCoverageMap } from '../components/search-jurisdictions/coverage-map.js';

const FIXTURE_DASHBOARD = {
  states: {
    co: {
      locality_gaps: {
        not_yet_scraped: [
          'ocd-division/country:us/state:co/place:greeley',
          'ocd-division/country:us/state:co/place:pueblo',
        ],
      },
    },
  },
};

describe('buildCoverageMap', () => {
  it('returns empty map when no dashboard data', () => {
    expect(buildCoverageMap(null, 'co')).toEqual({});
  });

  it('returns empty map when no state selected', () => {
    expect(buildCoverageMap(FIXTURE_DASHBOARD, '')).toEqual({});
  });

  it('maps unscraped ocdids to 0', () => {
    const result = buildCoverageMap(FIXTURE_DASHBOARD, 'co');
    expect(result['ocd-division/country:us/state:co/place:greeley']).toBe(0);
    expect(result['ocd-division/country:us/state:co/place:pueblo']).toBe(0);
  });

  it('returns empty map for state with no gaps', () => {
    const dashboard = { states: { co: { locality_gaps: { not_yet_scraped: [] } } } };
    expect(buildCoverageMap(dashboard, 'co')).toEqual({});
  });

  it('returns empty map when state not in dashboard', () => {
    expect(buildCoverageMap(FIXTURE_DASHBOARD, 'tx')).toEqual({});
  });
});
