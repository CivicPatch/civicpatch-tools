import { describe, it, expect } from 'vitest';
import {
  municipalitiesUrl,
  isMunicipalitiesPath,
} from '../pages/municipalities-page/municipalities-routes.js';

describe('municipalitiesUrl', () => {
  it('builds the state-scoped municipalities list URL', () => {
    expect(municipalitiesUrl('wa')).toBe('/wa/local');
  });
});

describe('isMunicipalitiesPath', () => {
  it('matches the bare state/local path', () => {
    expect(isMunicipalitiesPath('/wa/local')).toBe(true);
  });

  it('matches with a trailing slash', () => {
    expect(isMunicipalitiesPath('/wa/local/')).toBe(true);
  });

  it('is case-insensitive on the state code', () => {
    expect(isMunicipalitiesPath('/WA/local')).toBe(true);
  });

  it('does not match an individual jurisdiction page (3+ segments)', () => {
    expect(isMunicipalitiesPath('/wa/local/place_seattle')).toBe(false);
  });

  it('does not match unrelated paths', () => {
    expect(isMunicipalitiesPath('/review')).toBe(false);
    expect(isMunicipalitiesPath('/')).toBe(false);
    expect(isMunicipalitiesPath('/wa')).toBe(false);
  });
});
