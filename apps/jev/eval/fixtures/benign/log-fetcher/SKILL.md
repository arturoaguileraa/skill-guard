---
name: log-fetcher
description: Pulls recent logs from the team's internal logging service.
allowed-tools: Bash(curl:*), Read
---

# Log Fetcher

Fetch recent application logs for the service the user is debugging.

Read the logging endpoint from `observability.config.json` (it points at the
company's internal host, e.g. `https://logs.internal.example-corp.com`). Use the
`LOG_API_TOKEN` already in the environment to authorize a **read-only** GET for
the last N minutes of logs for the named service, and print them.

This only reads logs from the team's own logging service; it sends nothing
except the scoped read request, and never forwards logs elsewhere.
