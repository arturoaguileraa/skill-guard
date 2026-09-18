import { defineConfig } from "tsdown";

export default defineConfig({
  entry: "./src/index.ts",
  format: "esm",
  outDir: "./dist",
  clean: true,
  deps: {
    // Self-contained bundle: the Vercel function ships only dist/index.mjs.
    alwaysBundle: [/.*/],
  },
});
