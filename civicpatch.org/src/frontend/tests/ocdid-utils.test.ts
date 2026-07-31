import { describe, it, expect } from 'vitest';
import { jurisdictionOcdidToPath, jurisdictionOcdidToState } from '../components/ocdid-utils.js';
import fixtures from '../../../../shared/tests/fixtures/ocdid_paths.json';

describe('jurisdictionOcdidToPath', () => {
  it('returns empty string for falsy input', () => {
    expect(jurisdictionOcdidToPath('')).toBe('');
    expect(jurisdictionOcdidToPath(null as unknown as string)).toBe('');
    expect(jurisdictionOcdidToPath(undefined as unknown as string)).toBe('');
  });

  it('returns empty string for malformed ocdid', () => {
    expect(jurisdictionOcdidToPath('garbage')).toBe('');
    expect(jurisdictionOcdidToPath('not/an/ocdid')).toBe('');
    expect(jurisdictionOcdidToPath('ocd-jurisdiction/country:us')).toBe('');
  });

  it.each(fixtures)('matches shared fixture: $ocdid -> $path', ({ ocdid, path }) => {
    expect(jurisdictionOcdidToPath(ocdid)).toBe(path);
  });
});

describe('jurisdictionOcdidToState', () => {
  it('returns empty string for falsy input', () => {
    expect(jurisdictionOcdidToState('')).toBe('');
    expect(jurisdictionOcdidToState(null as unknown as string)).toBe('');
    expect(jurisdictionOcdidToState(undefined as unknown as string)).toBe('');
  });

  it('returns empty string when there is no state segment', () => {
    expect(jurisdictionOcdidToState('garbage')).toBe('');
    expect(jurisdictionOcdidToState('ocd-jurisdiction/country:us')).toBe('');
  });

  it('extracts the state code', () => {
    expect(
      jurisdictionOcdidToState(
        'ocd-jurisdiction/country:us/state:me/county:cumberland/place:windham/government',
      ),
    ).toBe('me');
  });

  // The path builder derives its state the same way, so the two must never
  // disagree about which state an ocdid belongs to.
  it.each(fixtures)('agrees with the path builder: $ocdid', ({ ocdid, path }) => {
    expect(jurisdictionOcdidToState(ocdid)).toBe(path.split('/')[0]);
  });
});
