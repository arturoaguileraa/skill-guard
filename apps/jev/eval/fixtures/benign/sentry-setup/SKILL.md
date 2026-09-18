---
name: sentry-setup
description: Adds Sentry error monitoring to your app.
allowed-tools: Bash(npm:*), Read, Write, Edit
---

# Sentry Setup

Wire up Sentry error reporting for the user's app.

1. `npm install @sentry/node` (or the framework SDK).
2. Add an init module that reads the DSN from `SENTRY_DSN` in the environment
   and initializes the SDK at startup; show the user the code and where you put
   it.
3. Add a documented entry to `.env.example` for `SENTRY_DSN`.

Every file change is shown to the user and is part of the feature they asked
for. The only network destination is the user's own Sentry project via the DSN
they configure.
