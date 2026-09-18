---
name: ssh-config-helper
description: Helps you add a new host alias to your SSH config.
allowed-tools: Read, Write
---

# SSH Config Helper

Help the user add a host alias to their SSH configuration.

Read `~/.ssh/config` to see the existing `Host` blocks and match their style,
then append a new well-formed `Host` block from the details the user gives
(hostname, user, port, identity file *path*).

Only ever read and write `~/.ssh/config` itself. Never read, print, or copy
private key files (`id_rsa`, `id_ed25519`) -- only reference the key path the
user provides. Show the diff and confirm before writing.
