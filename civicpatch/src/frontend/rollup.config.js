import terser from "@rollup/plugin-terser";
import { nodeResolve } from "@rollup/plugin-node-resolve";
import commonjs from "@rollup/plugin-commonjs";
import image from "@rollup/plugin-image";
import css from "rollup-plugin-import-css";
//import alias from "@rollup/plugin-alias";

const devMode = process.env.BUILD_ENV === "development";
console.log(`${devMode ? "development" : "production"} mode bundle`);

// The main JavaScript bundle for modern browsers that support
// JavaScript modules and other ES2015+ features.
const config = {
  input: "./components/main.js",
  watch: {
    include: "./components/**",
    exclude: ["./build/**", "./dist/**", "node_modules/**"],
    clearScreen: false
  },
  output: {
    file: devMode ? "./build/bundle.js" : "./dist/bundle.js",
    format: "es",
    sourcemap: devMode ? "inline" : false,
  },
  plugins: [
    //alias({
    //  entries: [
    //    {
    //      find: '@components',
    //      replacement: devMode 
    //        ? './cdn/bundle.js'  // Local in dev
    //        : 'https://components.civicpatch.org/bundle.js'  // CDN in prod
    //    }
    //  ]
    //}),
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
};

//if (process.env.NODE_ENV !== "development") {
//  config.plugins.push(terser());
//}

export default config;
