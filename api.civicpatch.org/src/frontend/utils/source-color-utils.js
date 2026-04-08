const COLOR_COUNT = 10;

function hashUrl(url) {
  let hash = 0;
  for (let i = 0; i < url.length; i++) {
    hash = (hash * 31 + url.charCodeAt(i)) >>> 0;
  }
  return hash;
}

// Fallback: hash-based color when no global map is available.
export function getSourceColorClass(url) {
  if (!url) return '';
  return `color-${(hashUrl(url) % COLOR_COUNT) + 1}`;
}

// Build a Map<url, { number, colorClass }> from an ordered sourceContentUrls array.
// number and colorClass are position-based so they stay consistent across components.
export function buildSourceUrlMap(sourceContentUrls = []) {
  const map = new Map();
  sourceContentUrls.forEach(({ url }, i) => {
    map.set(url, {
      number: i + 1,
      colorClass: `color-${(i % COLOR_COUNT) + 1}`,
    });
  });
  return map;
}
