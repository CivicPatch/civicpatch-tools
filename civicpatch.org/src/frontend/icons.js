// Every Font Awesome icon the app ships. This is the source of truth: the build
// subsets the webfonts down to exactly these, so an icon missing here renders blank.
//
// tests/icons.test.ts catches any `fa-solid fa-x` literal that is not listed. It cannot
// see names built at runtime, so those are listed here by hand and noted below.

// Includes names no scan can find: arrow-up/down (municipalities table),
// ATTENTION_COPY, FIELD_ICON, FALLBACK_ICONS (leaderboard), sun/moon (theme toggle).
export const SOLID = [
  "angles-up",
  "apple-whole",
  "arrow-down",
  "arrow-left",
  "arrow-right",
  "arrow-right-to-bracket",
  "arrow-up",
  "arrow-up-right-from-square",
  "beer-mug-empty",
  "bottle-water",
  "calendar-day",
  "calendar-xmark",
  "candy-cane",
  "caret-down",
  "carrot",
  "check",
  "chevron-down",
  "circle-check",
  "circle-exclamation",
  "circle-info",
  "clock-rotate-left",
  "cookie",
  "envelope",
  "flag",
  "gear",
  "grip-vertical",
  "ice-cream",
  "id-card",
  "landmark",
  "lemon",
  "link",
  "list-check",
  "location-dot",
  "lock",
  "magnifying-glass",
  "martini-glass",
  "moon",
  "mug-hot",
  "mug-saucer",
  "pen-to-square",
  "phone",
  "plus",
  "right-from-bracket",
  "right-to-bracket",
  "rotate",
  "rotate-left",
  "sun",
  "triangle-exclamation",
  "up-right-from-square",
  "wine-glass",
  "xmark",
];

export const REGULAR = [
  "copy",
];

export const BRANDS = [
  "github",
];
