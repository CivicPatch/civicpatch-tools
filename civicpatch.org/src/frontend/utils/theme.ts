export const THEME_MODE = {
  LIGHT: "light",
  DARK: "dark",
} as const;
export type ThemeMode = typeof THEME_MODE[keyof typeof THEME_MODE];

// `<html data-theme>` stays light/dark for mode-scoped CSS; `<html data-palette>` carries
// the id below, which tokens.css's colour blocks key on. A new theme is one entry here plus one block there.
export const THEMES: { id: string; name: string; mode: ThemeMode }[] = [
  { id: "one-light", name: "one light", mode: THEME_MODE.LIGHT },
  { id: "nord-light", name: "nord light", mode: THEME_MODE.LIGHT },
  { id: "nord-dark", name: "nord dark", mode: THEME_MODE.DARK },
  { id: "terminal", name: "terminal", mode: THEME_MODE.DARK },
];
const DEFAULT_PALETTE: Record<ThemeMode, string> = { light: "one-light", dark: "nord-dark" };

export interface ResolvedTheme {
  palette: string;
  mode: ThemeMode;
}

export function resolveTheme(savedTheme: string, systemMode: ThemeMode): ResolvedTheme {
  const saved = THEMES.find((t) => t.id === savedTheme);
  if (saved) return { palette: saved.id, mode: saved.mode };
  return { palette: DEFAULT_PALETTE[systemMode], mode: systemMode };
}
