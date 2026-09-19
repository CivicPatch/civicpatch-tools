import { describe, it, expect } from 'vitest';
import { resolveTheme, THEME_MODE } from '../utils/theme.js';

describe('resolveTheme', () => {
  it('uses a saved palette and its own mode, whatever the system mode', () => {
    expect(resolveTheme('terminal', THEME_MODE.LIGHT)).toEqual({ palette: 'terminal', mode: 'dark' });
  });

  it('falls back to the default palette for the system mode when nothing is saved', () => {
    expect(resolveTheme('', THEME_MODE.DARK)).toEqual({ palette: 'nord-dark', mode: 'dark' });
    expect(resolveTheme('', THEME_MODE.LIGHT)).toEqual({ palette: 'one-light', mode: 'light' });
  });

  it('falls back to the system default when the saved palette no longer exists', () => {
    expect(resolveTheme('dracula', THEME_MODE.DARK)).toEqual({ palette: 'nord-dark', mode: 'dark' });
  });
});
