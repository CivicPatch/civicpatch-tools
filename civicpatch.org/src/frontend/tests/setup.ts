// Runs before any test file is imported — vitest's node environment has no real window,
// but config.js reads window.ENV at module-load time, so the stub must exist before
// import hoisting evaluates it (a stub written inside a test file runs too late).
(globalThis as any).window = { ENV: { FRIENDLY_STORAGE_HOST: 'https://cdn.civicpatch.org' } };
