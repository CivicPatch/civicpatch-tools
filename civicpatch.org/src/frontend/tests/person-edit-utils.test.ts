import { describe, it, expect } from 'vitest';
import {
  parseDate,
  serializeDate,
  setDatePart,
  jurisdictionToDivisionBase,
  parseDivision,
  buildDivisionOcdid,
} from '../components/edit-people/person-edit-utils.js';

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
    expect(parseDivision(`${base}/council_district:1`, jurisdiction)).toEqual({ type: 'council_district', value: '1' });
    expect(parseDivision(`${base}/ward:3`, jurisdiction)).toEqual({ type: 'ward', value: '3' });
    expect(parseDivision(base, jurisdiction)).toEqual({ type: 'at_large', value: '' });
    expect(parseDivision('', jurisdiction)).toEqual({ type: 'at_large', value: '' });
    expect(parseDivision(`${base}/precinct:5`, jurisdiction)).toEqual({ type: 'other', value: '' });
  });

  it('treats a bare county/state-level division base as at-large, not "other"', () => {
    const countyJurisdiction = 'ocd-jurisdiction/country:us/state:co/county:pitkin/government';
    const countyBase = 'ocd-division/country:us/state:co/county:pitkin';
    expect(parseDivision(countyBase, countyJurisdiction)).toEqual({ type: 'at_large', value: '' });

    const stateJurisdiction = 'ocd-jurisdiction/country:us/state:co/government';
    const stateBase = 'ocd-division/country:us/state:co';
    expect(parseDivision(stateBase, stateJurisdiction)).toEqual({ type: 'at_large', value: '' });
  });

  it('builds OCD-IDs from type + value', () => {
    expect(buildDivisionOcdid(jurisdiction, 'at_large', '')).toBe(base);
    expect(buildDivisionOcdid(jurisdiction, 'council_district', '1')).toBe(`${base}/council_district:1`);
    expect(buildDivisionOcdid(jurisdiction, 'ward', '3')).toBe(`${base}/ward:3`);
  });

  it('round-trips recognized divisions through the jurisdiction', () => {
    for (const ocdid of [base, `${base}/council_district:1`, `${base}/ward:3`]) {
      const { type, value } = parseDivision(ocdid, jurisdiction);
      expect(buildDivisionOcdid(jurisdiction, type, value)).toBe(ocdid);
    }
  });
});

describe("setDatePart — cascade", () => {
  const parts = { year: "2021", month: "03", day: "04" };

  it("clears the day when the month is cleared", () => {
    expect(setDatePart(parts, "month", "")).toEqual({ year: "2021", month: "", day: "" });
  });

  it("clears month and day when the year is cleared", () => {
    // A month with no year is not a date anyone can act on — the record should
    // never be able to hold "March, no year".
    expect(setDatePart(parts, "year", "")).toEqual({ year: "", month: "", day: "" });
  });

  it("leaves finer parts alone when a value is set rather than cleared", () => {
    expect(setDatePart(parts, "year", "2022")).toEqual({ year: "2022", month: "03", day: "04" });
  });
});
