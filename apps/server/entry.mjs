// Vercel entrypoint. It must exist in git (validated before the build), while
// dist/ is a build artifact: the self-contained tsdown bundle from `build`.
export { default } from "./dist/index.mjs";
