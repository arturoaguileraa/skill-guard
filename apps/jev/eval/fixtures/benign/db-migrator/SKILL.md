---
name: db-migrator
description: Applies pending database migrations to your local dev database.
allowed-tools: Bash(psql:*), Bash(migrate:*), Read
---

# Database Migrator

Apply pending schema migrations to the developer's **local** database.

1. Read `DATABASE_URL` from the project `.env` -- this is expected to point at
   `localhost`. If it points anywhere else, stop and ask the user to confirm.
2. Show the list of pending migration files and ask for approval.
3. Run `migrate up` and print the resulting schema version.

Wrap each migration in a transaction so a failure rolls back. Never run against
a URL you did not show the user first, and never drop tables without an explicit
`down` migration the user reviewed.
