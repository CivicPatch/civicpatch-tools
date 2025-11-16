import terser from "@rollup/plugin-terser";
import { nodeResolve } from "@rollup/plugin-node-resolve";
import commonjs from "@rollup/plugin-commonjs";
import image from "@rollup/plugin-image";
import css from "rollup-plugin-import-css";

const devMode = process.env.BUILD_ENV === "development";
console.log(`${devMode ? "development" : "production"} mode bundle`);

// The main JavaScript bundle for modern browsers that support
// JavaScript modules and other ES2015+ features.
const config = [{
  input: "./src/index.js",
  watch: "./src/**",
  output: {
    file: devMode ? "./build/bundle.js" : "./dist/bundle.js",
    format: "es",
    sourcemap: devMode ? "inline" : false,
  },
  plugins: [
    nodeResolve(),
    image(),
    commonjs(),
    css(),
    terser({
      ecma: 2020,
      mangle: { toplevel: true },
      compress: {
        module: true,
        toplevel: true,
        unsafe_arrows: true,
        drop_console: !devMode,
        drop_debugger: !devMode,
      },
      output: { quote_style: 1 },
    }),
  ],
  // plugins: [minifyHTML(), copy(copyConfig), resolve()],
  // plugins: [copy(copyConfig), resolve()],
  // preserveEntrySignatures: false,
}];

//if (process.env.NODE_ENV !== "development") {
//  config.plugins.push(terser());
//}

export default config;
