---
name: env-doctor
description: Checks your .env against .env.example and reports what's missing.
allowed-tools: Read
---

# Env Doctor

Validate the project's environment configuration.

Read `.env.example` for the list of required keys, then read `.env` and compare.
Report which keys are missing, which are empty, and which are present in `.env`
but not documented in `.env.example`.

Only ever **read** these files, and only print the key *names* and a
present/absent/empty status -- never print or transmit any secret value. This
runs entirely locally.
