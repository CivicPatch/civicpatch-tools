import { describe, it, expect } from 'vitest';
import {
  parseDate,
  serializeDate,
  jurisdictionToDivisionBase,
  parseDivision,
  buildDivisionOcdid,
  toDraft,
  buildUpdates,
  type Person,
} from '../components/edit-people/person-edit-utils.js';

const denver: Person = {
  id: 'p1',
  name: 'Amanda Sandoval',
  office: { name: 'Council Member', division_ocdid: 'ocd-division/country:us/state:co/place:denver/council_district:1' },
  start_date: '2023',
  end_date: null,
  phones: ['(720) 337-7701'],
  emails: ['district1@denvergov.org'],
  urls: [],
  other_names: [],
  source_urls: ['https://denvergov.org/council'],
  jurisdiction_ocdid: 'ocd-jurisdiction/country:us/state:co/place:denver/government',
};

describe('parseDate / serializeDate', () => {
  it('parses partial and full dates', () => {
    expect(parseDate('2023')).toEqual({ year: '2023', month: '', day: '' });
    expect(parseDate('2023-11')).toEqual({ year: '2023', month: '11', day: '' });
    expect(parseDate('2023-11-15')).toEqual({ year: '2023', month: '11', day: '15' });
    expect(parseDate('')).toEqual({ year: '', month: '', day: '' });
    expect(parseDate(null)).toEqual({ year: '', month: '', day: '' });
  });

  it('serializes from the first empty part onward', () => {
    expect(serializeDate({ year: '', month: '', day: '' })).toBe('');
    expect(serializeDate({ year: '2023', month: '', day: '' })).toBe('2023');
    expect(serializeDate({ year: '2023', month: '11', day: '' })).toBe('2023-11');
    expect(serializeDate({ year: '2023', month: '11', day: '15' })).toBe('2023-11-15');
    // a day with no month can't form a valid string — month gates it
    expect(serializeDate({ year: '2023', month: '', day: '15' })).toBe('2023');
  });

  it('round-trips every precision', () => {
    for (const v of ['', '2023', '2023-11', '2023-11-15']) {
      expect(serializeDate(parseDate(v))).toBe(v);
    }
  });
});

describe('division OCD-ID', () => {
  const jurisdiction = 'ocd-jurisdiction/country:us/state:co/place:denver/government';
  const base = 'ocd-division/country:us/state:co/place:denver';

  it('derives the division base from the jurisdiction', () => {
    expect(jurisdictionToDivisionBase(jurisdiction)).toBe(base);
    expect(jurisdictionToDivisionBase('')).toBe('');
    expect(jurisdictionToDivisionBase(null)).toBe('');
  });

  it('parses recognized division types', () => {
    expect(parseDivision(`${base}/council_district:1`)).toEqual({ type: 'council_district', value: '1' });
    expect(parseDivision(`${base}/ward:3`)).toEqual({ type: 'ward', value: '3' });
    expect(parseDivision(base)).toEqual({ type: 'at_large', value: '' });
    expect(parseDivision('')).toEqual({ type: 'at_large', value: '' });
    expect(parseDivision(`${base}/precinct:5`)).toEqual({ type: 'other', value: '' });
  });

  it('builds OCD-IDs from type + value', () => {
    expect(buildDivisionOcdid(jurisdiction, 'at_large', '')).toBe(base);
    expect(buildDivisionOcdid(jurisdiction, 'council_district', '1')).toBe(`${base}/council_district:1`);
    expect(buildDivisionOcdid(jurisdiction, 'ward', '3')).toBe(`${base}/ward:3`);
  });

  it('round-trips recognized divisions through the jurisdiction', () => {
    for (const ocdid of [base, `${base}/council_district:1`, `${base}/ward:3`]) {
      const { type, value } = parseDivision(ocdid);
      expect(buildDivisionOcdid(jurisdiction, type, value)).toBe(ocdid);
    }
  });
});

describe('buildUpdates', () => {
  it('sends nothing when the draft is unchanged', () => {
    expect(buildUpdates(denver, toDraft(denver), denver.jurisdiction_ocdid!)).toEqual({});
  });

  it('sends only the changed top-level field', () => {
    const draft = { ...toDraft(denver), name: 'Amanda P. Sandoval' };
    expect(buildUpdates(denver, draft, denver.jurisdiction_ocdid!)).toEqual({ name: 'Amanda P. Sandoval' });
  });

  it('sends a cleared date as null', () => {
    const draft = { ...toDraft(denver), startDate: { year: '', month: '', day: '' } };
    expect(buildUpdates(denver, draft, denver.jurisdiction_ocdid!)).toEqual({ start_date: null });
  });

  it('does not mark an already-empty date dirty', () => {
    // end_date is null; an untouched empty draft must not appear in updates
    expect(buildUpdates(denver, toDraft(denver), denver.jurisdiction_ocdid!)).not.toHaveProperty('end_date');
  });

  it('sends office as a whole object with the rebuilt division OCD-ID', () => {
    const draft = { ...toDraft(denver), divisionType: 'ward' as const, divisionValue: '2' };
    expect(buildUpdates(denver, draft, denver.jurisdiction_ocdid!)).toEqual({
      office: { name: 'Council Member', division_ocdid: 'ocd-division/country:us/state:co/place:denver/ward:2' },
    });
  });

  it('preserves a legacy "other" division untouched', () => {
    const precinct: Person = {
      ...denver,
      office: { name: 'Trustee', division_ocdid: 'ocd-division/country:us/state:co/place:denver/precinct:5' },
    };
    // toDraft maps precinct -> "other"; an unchanged save must not touch office
    expect(buildUpdates(precinct, toDraft(precinct), precinct.jurisdiction_ocdid!)).not.toHaveProperty('office');
  });

  it('sends an edited multi-value array', () => {
    const draft = { ...toDraft(denver), phones: ['(720) 337-7701', '(303) 555-0000'] };
    expect(buildUpdates(denver, draft, denver.jurisdiction_ocdid!)).toEqual({ phones: ['(720) 337-7701', '(303) 555-0000'] });
  });
});
