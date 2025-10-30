import { fromRollup } from "@web/dev-server-rollup";
import rollupCommonjs from "@rollup/plugin-commonjs";
const commonjs = fromRollup(rollupCommonjs);

export default {
  port: 8002,
  watch: false,
  open: false,

  nodeResolve: true,
  plugins: [
    commonjs({
      include: [
        "./node_modules/leaflet/**/*",
        "./node_modules/leaflet.locatecontrol/**/*",
      ],
    }),
  ],
  // rootDir: ".",
  // /src/frontend/static",

  // Add debug logging
  //plugins: [
  //  commonjs({
  //    include: ["**/node_modules/leaflet/**/*"],
  //  }),
  //],
  debug: true,
};
