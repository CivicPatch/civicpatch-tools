import { useLocalStorage, PERSIST_FOREVER } from "./use-local-storage.js";
import { STORAGE_KEYS } from "../utils/storage-keys.js";
import { resolveTheme, THEME_MODE, type ResolvedTheme, type ThemeMode } from "../utils/theme.js";

function readSystemMode(): ThemeMode {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? THEME_MODE.DARK
    : THEME_MODE.LIGHT;
}

export function useTheme(): [ResolvedTheme, (palette: string) => void] {
  const [savedTheme, setSavedTheme] = useLocalStorage(STORAGE_KEYS.THEME, "", {
    ttl: PERSIST_FOREVER,
  });
  return [resolveTheme(savedTheme, readSystemMode()), setSavedTheme];
}
