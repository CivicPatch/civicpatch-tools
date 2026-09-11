// Vite entry for the global stylesheets loaded on every page (base.html). Bundling them as a
// real entry — rather than base.html linking the source files directly — gives them a
// content-hashed, immutable-cacheable output under /build/assets/, same as every page's own
// script. Import order matters: tokens.css's `@layer base, layout, components, utilities;`
// must be the first layer statement Vite/the browser sees, or layer priority is wrong.
//
// fonts.css is deliberately NOT here — Vite rewrites its @font-face url()s to hashed asset
// paths, which would stop matching the <link rel="preload"> hrefs in base.html (those name the
// plain /fonts/*.woff2 path). It stays a direct, unhashed link; font files change rarely enough
// that the staleness risk this fixes for everything else barely applies to them.
import "../css/tokens.css";
import "../css/elements.css";
import "../css/typography.css";
import "../css/controls.css";
import "../css/layout.css";
import "../css/styles.css";
import "../css/utilities.css";
