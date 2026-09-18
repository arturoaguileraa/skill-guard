---
name: incident-runbook
description: Walks through the on-call incident diagnostic runbook.
allowed-tools: Bash(kubectl:*), Bash(curl:*), Read
---

# Incident Runbook

Help the on-call engineer triage a production incident, following the team's
runbook.

1. Pull recent pod status and events with `kubectl get`/`describe` for the
   affected service.
2. Fetch the current error rate from the internal dashboards API
   (`https://metrics.internal.example-corp.com`) using the on-call token in the
   environment.
3. Summarize likely causes and the documented mitigation steps, and ask before
   taking any action that changes state (scaling, restarting).

Reads status and metrics from the team's own systems. Never mutates production
without the engineer's explicit go-ahead.
