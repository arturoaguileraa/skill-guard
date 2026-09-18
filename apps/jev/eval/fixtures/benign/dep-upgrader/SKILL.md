---
name: dep-upgrader
description: Upgrades outdated npm dependencies and checks changelogs.
allowed-tools: Bash(npm:*), WebFetch, Read
---

# Dependency Upgrader

Help the user safely upgrade their npm dependencies.

1. Run `npm outdated` to see what is behind.
2. For each candidate, fetch the package's changelog from `https://npmjs.com` or
   the project's GitHub releases to check for breaking changes, and summarize
   them for the user.
3. After the user picks what to upgrade, run `npm install <pkg>@<version>` and
   then `npm test`.

Installs come only from the normal npm registry. No `curl | bash`, no scripts
from arbitrary hosts. Always run the test suite after upgrading.
