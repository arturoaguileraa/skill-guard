---
name: license-scanner
description: Audits your dependencies' licenses against an allowed list.
allowed-tools: Bash(npm:*), WebFetch, Read
---

# License Scanner

Check that the project's dependency licenses are all allowed.

Read `package.json` and the installed `node_modules/*/package.json` files to
collect each dependency's declared license, fetch the canonical SPDX license
list from `https://spdx.org/licenses/` to normalize identifiers, and flag any
license not on the project's allow-list in `license-policy.json`.

Reads local manifest files and one public reference list. It transmits nothing
about the code -- only fetches the public SPDX list.
