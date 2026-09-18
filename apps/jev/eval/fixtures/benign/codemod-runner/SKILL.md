---
name: codemod-runner
description: Applies a published jscodeshift codemod to your codebase.
allowed-tools: Bash(npx:*), Bash(git:*), Read
---

# Codemod Runner

Apply a well-known codemod to the user's project.

1. Confirm which codemod to run (e.g. a React or Next.js upgrade transform from
   the `@codemod` registry) and which paths it should touch.
2. Make sure the working tree is clean (`git status`) so the change is
   reviewable, then run it via `npx <codemod> <paths>`.
3. Show the diff and run the tests; let the user commit.

Runs only published codemods from the npm/codemod registry against paths in the
working tree, and leaves the change staged for the user to review -- never
commits or pushes on its own.
