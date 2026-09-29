import { describe, it, expect } from 'vitest';
import { changedFields } from '../pages/jurisdictions-page/jurisdiction-edit.js';

const SAVED = { url: 'https://seattle.gov', government_form: 'mayor_council' };

describe('changedFields', () => {
  it('is empty when nothing moved', () => {
    expect(changedFields(SAVED, { ...SAVED })).toEqual({});
  });

  it('carries only the fields that changed', () => {
    expect(changedFields(SAVED, { ...SAVED, url: 'https://seattle.gov/new' })).toEqual({
      url: 'https://seattle.gov/new',
    });
    expect(changedFields(SAVED, { ...SAVED, government_form: 'council_manager' })).toEqual({
      government_form: 'council_manager',
    });
  });

  it('sends an emptied url, which clears the website', () => {
    expect(changedFields(SAVED, { ...SAVED, url: '' })).toEqual({ url: '' });
  });

  it('never sends an emptied government form: "Not known" writes nothing', () => {
    expect(changedFields(SAVED, { ...SAVED, government_form: '' })).toEqual({});
  });
});
