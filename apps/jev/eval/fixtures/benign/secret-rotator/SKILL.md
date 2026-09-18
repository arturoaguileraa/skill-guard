---
name: secret-rotator
description: Rotates an exposed API key following your provider's runbook.
allowed-tools: Bash(aws:*), Bash(gh:*), Read
---

# Secret Rotator

Rotate a credential the user tells you has leaked. This is a destructive,
irreversible action, so it is gated on explicit confirmation at every step.

1. Ask the user exactly which credential to rotate and in which account.
2. Create the *new* credential first and show it to the user so they can update
   their secret store.
3. Only after the user confirms the new key works, revoke the old one
   (`aws iam delete-access-key` / `gh auth token` rotation) -- and confirm once
   more before the irreversible revoke.

Never revoke a credential you were not explicitly asked to rotate, and never
skip the confirmations even if asked to "just do it fast".
