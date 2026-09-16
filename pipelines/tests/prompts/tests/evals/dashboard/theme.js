// Mirrors civicpatch.org's navbar.js THEMES: a palette added there needs adding here.
(function () {
  const THEME_STORAGE_KEY = "app:theme";
  const THEME_PICKER_ID = "theme-picker";
  const THEMES = [
    { id: "one-light", name: "one light", mode: "light" },
    { id: "nord-light", name: "nord light", mode: "light" },
    { id: "nord-dark", name: "nord dark", mode: "dark" },
    { id: "terminal", name: "terminal", mode: "dark" },
  ];
  const DEFAULT_PALETTE = { light: "one-light", dark: "nord-dark" };
  const MODES = ["dark", "light"];

  function applyPalette(id) {
    let theme = THEMES.find((t) => t.id === id);
    if (!theme) {
      const mode = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      theme = THEMES.find((t) => t.id === DEFAULT_PALETTE[mode]);
    }
    document.documentElement.dataset.theme = theme.mode;
    document.documentElement.dataset.palette = theme.id;
  }

  function readStoredPalette() {
    try {
      return (JSON.parse(localStorage.getItem(THEME_STORAGE_KEY)) || {}).__value;
    } catch (err) {
      return null;
    }
  }

  // Same {__value, __expiresAt} envelope as the app's useLocalStorage.
  function storePalette(id) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ __value: id, __expiresAt: null }));
    } catch (err) {
      // Storage blocked; the palette still applies to this page view.
    }
  }

  function fillPicker() {
    const picker = document.getElementById(THEME_PICKER_ID);
    for (const mode of MODES) {
      const group = document.createElement("optgroup");
      group.label = mode;
      for (const theme of THEMES.filter((t) => t.mode === mode)) {
        group.append(new Option(theme.name, theme.id));
      }
      picker.append(group);
    }
    picker.value = document.documentElement.dataset.palette;
    picker.addEventListener("change", (e) => {
      applyPalette(e.target.value);
      storePalette(e.target.value);
    });
  }

  applyPalette(readStoredPalette());
  document.addEventListener("DOMContentLoaded", fillPicker);
})();
