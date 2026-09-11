import { defineConfig } from "vite";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/frontend/build/" : "/",
  build: {
    outDir: "build",
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        "global-styles": "./assets/global-styles.js",
        index: "./assets/index.js",
        review: "./assets/review.ts",
        "review-session": "./assets/review-session.ts",
        "bulk-review": "./assets/bulk-review.js",
        issues: "./assets/issues.js",
        jurisdiction: "./assets/jurisdiction.js",
        "jurisdiction-history": "./assets/jurisdiction-history.ts",
        login: "./assets/login.ts",
        "login-username": "./assets/login-username.ts",
        admin: "./assets/admin.ts",
        activity: "./assets/activity.ts",
        roles: "./assets/roles.js",
        settings: "./assets/settings.ts",
        municipalities: "./assets/municipalities.ts",
        imports: "./assets/imports.ts",
        changesets: "./assets/changesets.ts",
        spend: "./assets/spend.ts",
        pipelines: "./assets/pipelines.ts",
        gallery: "./assets/gallery.ts",
        "user-profile": "./assets/user-profile.ts",
        "user-history": "./assets/user-history.ts",
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 8004,
    origin: "http://localhost:8004",
  },
}));
