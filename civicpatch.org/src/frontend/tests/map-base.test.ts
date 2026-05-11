import { describe, it, expect } from 'vitest';
import { pmtilesUrl, stateFromOcdid, getVisibleLayers } from '../components/map/map-base.js';

describe('pmtilesUrl', () => {
  it('returns pmtiles URL for a state', () => {
    expect(pmtilesUrl('co')).toBe('pmtiles://cdn.civicpatch.org/maps/co.pmtiles');
  });
});

describe('stateFromOcdid', () => {
  it('extracts state code from ocdid', () => {
    expect(stateFromOcdid('ocd-division/country:us/state:co/place:denver')).toBe('co');
  });

  it('returns null for ocdid without state', () => {
    expect(stateFromOcdid('ocd-division/country:us')).toBeNull();
  });
});

describe('getVisibleLayers', () => {
  it('national level shows only states', () => {
    expect(getVisibleLayers('national')).toEqual(['states']);
  });

  it('counties level shows states and counties', () => {
    expect(getVisibleLayers('counties')).toEqual(['states', 'counties']);
  });

  it('local level shows only local', () => {
    expect(getVisibleLayers('local')).toEqual(['local']);
  });
});
