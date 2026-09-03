import { describe, it, expect } from 'vitest';
import {
  jurisdictionOcdidToPath,
  jurisdictionOcdidToState,
  divisionOcdidToFriendly,
  parseDivision,
} from '../components/ocdid-utils.js';
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

  // Was: `toBe(path)` against the shared folder fixture, which this and
  // pipelines/tests/unit/utils/test_id_utils.py both read to keep two encoders in agreement.
  // A jurisdiction page's URL is now its ocdid, so JS has no folder encoder left to agree
  // about — the fixture still guards the Python one, which open-data's directory layout needs.
  it.each(fixtures)('a page url is the ocdid itself: $ocdid', ({ ocdid }) => {
    expect(jurisdictionOcdidToPath(ocdid)).toBe(encodeURI(ocdid));
    expect(decodeURI(jurisdictionOcdidToPath(ocdid))).toBe(ocdid);
  });

  it('keeps slashes and colons literal, and escapes only what must be', () => {
    const withAccent =
      'ocd-jurisdiction/country:us/state:ca/place:la_ca\u00f1ada_flintridge/government';
    expect(jurisdictionOcdidToPath(withAccent)).toBe(
      'ocd-jurisdiction/country:us/state:ca/place:la_ca%C3%B1ada_flintridge/government',
    );
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

  // Both readers go through the same segment parse, so they cannot disagree about what
  // counts as an ocdid. The path builder no longer derives a state at all — a page url is
  // the ocdid itself.
  it.each(fixtures)('agrees with the path builder: $ocdid', ({ ocdid, path }) => {
    expect(jurisdictionOcdidToState(ocdid)).toBe(path.split('/')[0]);
  });
});


// Written 2026-08-20 when `parseDivision` was extracted so `divisionName` could share it.
// The function had no coverage, so the refactor was unverified until these existed.
describe('divisionOcdidToFriendly', () => {
  const base = 'ocd-division/country:us/state:wa/place:seattle';

  it('renders districts and wards as compact badges', () => {
    expect(divisionOcdidToFriendly(`${base}/council_district:3`)).toBe('[D3]');
    expect(divisionOcdidToFriendly(`${base}/ward:1`)).toBe('[W1]');
  });

  it('renders a whole-jurisdiction division as nothing', () => {
    // Deliberate here: the badge sits beside a name, and "place:seattle" adds nothing a
    // reader on a Seattle page does not already know. `divisionName` makes the opposite
    // choice for a row heading, which is why only the parse is shared.
    expect(divisionOcdidToFriendly(base)).toBe('');
  });

  it('falls back to the raw designation for anything unrecognised', () => {
    expect(divisionOcdidToFriendly(`${base}/precinct:12`)).toBe('precinct 12');
  });

  it('returns empty string for falsy input', () => {
    expect(divisionOcdidToFriendly('')).toBe('');
    expect(divisionOcdidToFriendly(null as unknown as string)).toBe('');
  });
});

describe('parseDivision', () => {
  it('splits the last segment into designation and value', () => {
    expect(parseDivision('ocd-division/country:us/state:wa/place:x/ward:3')).toEqual({
      key: 'ward',
      value: '3',
    });
  });

  it('survives a missing value and a missing input', () => {
    expect(parseDivision('ward')).toEqual({ key: 'ward', value: '' });
    expect(parseDivision(undefined as unknown as string)).toEqual({ key: '', value: '' });
  });
});
