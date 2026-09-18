---
name: commit-helper
description: Writes a clear conventional-commit message from your staged changes.
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git commit:*)
---

# Commit Helper

Generate a good commit message for the user's staged changes.

Inspect the change with `git diff --staged` and recent history with
`git log --oneline -n 20` to match the repo's message style. Draft a
conventional-commit message (`type(scope): summary`) with a short body
explaining *why*.

Show the message to the user and let them edit it. Only run `git commit` once
they approve. Do not push, do not amend published commits, and do not use
`--no-verify`.
