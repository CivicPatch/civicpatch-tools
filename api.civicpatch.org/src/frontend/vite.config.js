import { defineConfig } from "vite";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/frontend/build/" : "/",
  build: {
    outDir: "build",
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        index: "./assets/index.js",
        review: "./assets/review.js",
        queue: "./assets/queue.js",
        issues: "./assets/issues.js",
        jurisdiction: "./assets/jurisdiction.js",
        progress: "./assets/progress.js",
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    origin: "http://localhost:5173",
  },
}));
