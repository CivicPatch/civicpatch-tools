import { describe, it, expect } from 'vitest';
import { changedFields } from '../pages/jurisdictions-page/jurisdiction-edit.js';

const SAVED = { url: 'https://seattle.gov' };

describe('changedFields', () => {
  it('is empty when nothing moved', () => {
    expect(changedFields(SAVED, { ...SAVED })).toEqual({});
  });

  it('carries the url when it changed', () => {
    expect(changedFields(SAVED, { url: 'https://seattle.gov/new' })).toEqual({
      url: 'https://seattle.gov/new',
    });
  });

  it('sends an emptied url, which clears the website', () => {
    expect(changedFields(SAVED, { url: '' })).toEqual({ url: '' });
  });
});
