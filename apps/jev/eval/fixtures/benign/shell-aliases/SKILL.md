---
name: shell-aliases
description: Adds convenient project aliases to your shell profile.
allowed-tools: Read, Write
---

# Shell Aliases

Set up handy shell aliases for the current project.

Propose a small set of aliases (e.g. `alias dc='docker compose'`) and **show the
exact lines to the user first**. On approval, append them to `~/.zshrc` inside a
clearly marked `# >>> project aliases >>>` ... `# <<< project aliases <<<`
block so they are easy to find and remove.

This does modify a shell rc file -- but only with visible, user-approved
aliases inside a labeled block, and it runs no commands and fetches nothing.
