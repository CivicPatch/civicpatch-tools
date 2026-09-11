import { describe, it, expect } from 'vitest';
import { assignLetters } from '../components/nav-shortcuts/letters.js';

describe('assignLetters', () => {
  it('picks the first unused letter that appears in the label', () => {
    const result = assignLetters([{ label: 'Home' }, { label: 'Blog' }]);
    expect(result[0].letter).toBe('h');
    expect(result[1].letter).toBe('b');
  });

  it('never assigns the same letter twice, even when labels share letters', () => {
    const result = assignLetters([
      { label: 'Manage' },
      { label: 'Admin' },
      { label: 'Activity' },
    ]);
    const letters = result.map((r: { letter: string }) => r.letter);
    expect(new Set(letters).size).toBe(letters.length);
  });

  it('falls back to any free letter once every letter in the label is taken', () => {
    const result = assignLetters([{ label: 'aa' }, { label: 'aa' }]);
    expect(result[0].letter).toBe('a');
    expect(result[1].letter).not.toBe('a');
  });
});
