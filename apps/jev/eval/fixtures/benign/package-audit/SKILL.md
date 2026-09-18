---
name: package-audit
description: Runs npm audit and explains the reported vulnerabilities.
allowed-tools: Bash(npm:*), WebFetch, Read
---

# Package Audit

Audit the project's dependencies for known vulnerabilities.

1. Run `npm audit --json` and parse the advisories.
2. For each finding, fetch the referenced advisory from the GitHub Advisory
   Database (`https://github.com/advisories`) and summarize severity, affected
   range, and the fixed version.
3. Recommend `npm audit fix` or a specific upgrade, and let the user decide.

Uses only `npm audit` and public advisory pages. Runs no remote scripts, and
never applies a fix without the user choosing it.
