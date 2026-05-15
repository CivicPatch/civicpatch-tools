import { describe, it, expect } from 'vitest';
import { jurisdictionOcdidToPath } from '../components/ocdid-utils.js';
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
