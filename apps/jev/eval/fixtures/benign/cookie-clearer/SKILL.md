---
name: e2e-cookie-reset
description: Clears the test browser profile's cookies between E2E runs.
allowed-tools: Bash(rm:*), Read
---

# E2E Cookie Reset

Reset the **dedicated test** browser profile between end-to-end runs so tests
start clean.

Remove the `Cookies` and `Local Storage` files under the Playwright/Chromium
*test* profile directory (`./.e2e-profile/`), which the test harness recreates
on the next run.

Only ever touches the throwaway `./.e2e-profile/` inside the project. Never
reads cookie contents, and never touches the user's real browser profile in
`~/Library` or `~/.config`.
