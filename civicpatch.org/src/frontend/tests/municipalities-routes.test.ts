import { describe, it, expect } from 'vitest';
import {
  municipalitiesUrl,
  countiesUrl,
  isMunicipalitiesPath,
  isCountiesPath,
} from '../pages/municipalities-page/municipalities-routes.js';

describe('municipalitiesUrl', () => {
  it('builds the state-scoped municipalities list URL', () => {
    expect(municipalitiesUrl('wa')).toBe('/wa/municipalities');
  });
});

describe('countiesUrl', () => {
  it('builds the state-scoped counties list URL', () => {
    expect(countiesUrl('wa')).toBe('/wa/counties');
  });
});

describe('isMunicipalitiesPath', () => {
  it('matches the state/municipalities path', () => {
    expect(isMunicipalitiesPath('/wa/municipalities')).toBe(true);
  });

  it('matches with a trailing slash', () => {
    expect(isMunicipalitiesPath('/wa/municipalities/')).toBe(true);
  });

  it('is case-insensitive on the state code', () => {
    expect(isMunicipalitiesPath('/WA/municipalities')).toBe(true);
  });

  it('does not match the counties path', () => {
    expect(isMunicipalitiesPath('/wa/counties')).toBe(false);
  });

  it('does not match a bare state path', () => {
    expect(isMunicipalitiesPath('/wa')).toBe(false);
  });

  it('does not match an individual jurisdiction page (2+ extra segments)', () => {
    expect(isMunicipalitiesPath('/wa/local/place_seattle')).toBe(false);
  });

  it('does not match unrelated paths', () => {
    expect(isMunicipalitiesPath('/review')).toBe(false);
    expect(isMunicipalitiesPath('/')).toBe(false);
  });
});

describe('isCountiesPath', () => {
  it('matches the state/counties path', () => {
    expect(isCountiesPath('/wa/counties')).toBe(true);
  });

  it('matches with a trailing slash', () => {
    expect(isCountiesPath('/wa/counties/')).toBe(true);
  });

  it('is case-insensitive on the state code', () => {
    expect(isCountiesPath('/WA/counties')).toBe(true);
  });

  it('does not match the municipalities path', () => {
    expect(isCountiesPath('/wa/municipalities')).toBe(false);
  });

  it('does not match unrelated paths', () => {
    expect(isCountiesPath('/review')).toBe(false);
    expect(isCountiesPath('/')).toBe(false);
  });
});
