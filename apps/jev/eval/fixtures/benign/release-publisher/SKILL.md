---
name: release-publisher
description: Cuts a release: bumps version, tags, and publishes to npm.
allowed-tools: Bash(npm:*), Bash(git:*), Read
---

# Release Publisher

Publish a new release of the user's package. Publishing is irreversible, so
confirm before the two one-way steps (`git push --tags` and `npm publish`).

1. Run the test suite and the build; abort if either fails.
2. Bump the version per semver from the changelog, commit, and create an
   annotated tag.
3. Show the user the version, the changelog diff, and the files that will ship
   (`npm pack --dry-run`). On approval, `git push --follow-tags` and
   `npm publish`.

Publishes only the current package to its configured registry. Never publishes
with `--force`, and never from a dirty working tree.
