---
name: api-tester
description: Runs smoke tests against your local API with curl.
allowed-tools: Bash(curl:*), Read
---

# API Smoke Tester

Smoke-test the user's API.

Read the base URL from the project's `test.config.json` (defaults to
`http://localhost:8080`). For each endpoint in the config, `curl` it with the
sample request body and assert the status code and a couple of fields, then
print a pass/fail table.

Only calls the URL the user configured (their own service). Uses no credentials
beyond a test token in the config, and posts only the sample fixtures, never
real data.
