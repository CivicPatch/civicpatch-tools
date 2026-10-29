import { describe, it, expect } from 'vitest';
import { civicpatchHasNoOne } from '../pages/roster-comparison-page/jurisdictions.js';
import type { OutcomeCounts } from '../pages/roster-comparison-page/types.js';

const NOBODY: OutcomeCounts = {
  matched: 0,
  possible_match: 0,
  only_in_uploaded_data: 6,
  only_in_civicpatch: 0,
  only_in_civicpatch_not_compared: 0,
};

describe('civicpatchHasNoOne', () => {
  it('is true when every row is only in the uploaded data', () => {
    expect(civicpatchHasNoOne(NOBODY)).toBe(true);
  });

  it('is false when civicpatch has anyone there, even only in organizations not compared', () => {
    expect(civicpatchHasNoOne({ ...NOBODY, matched: 1 })).toBe(false);
    expect(civicpatchHasNoOne({ ...NOBODY, possible_match: 1 })).toBe(false);
    expect(civicpatchHasNoOne({ ...NOBODY, only_in_civicpatch: 1 })).toBe(false);
    expect(civicpatchHasNoOne({ ...NOBODY, only_in_civicpatch_not_compared: 1 })).toBe(false);
  });
});
