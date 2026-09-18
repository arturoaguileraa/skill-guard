---
name: docker-cleaner
description: Reclaims disk by pruning stopped containers and dangling images.
allowed-tools: Bash(docker:*), Bash(rm:*)
---

# Docker Cleaner

Reclaim disk space from Docker safely.

1. Show the user what would be removed first: `docker system df` and
   `docker image ls -f dangling=true`.
2. On approval, run `docker container prune` and `docker image prune` (dangling
   only, not `-a` unless the user asks).
3. Optionally remove the local `./build/` and `./dist/` output directories in
   the current project.

Only ever deletes Docker's own reclaimable data and build output *inside the
project directory*. Never touches files outside the working tree, never uses
`docker system prune -a --volumes` without a clear warning and confirmation.
