---
name: data-anonymizer
description: Produces an anonymized copy of a dataset for local testing.
allowed-tools: Bash(python3:*), Read, Write
---

# Data Anonymizer

Create a safe, anonymized copy of a dataset so it can be used in tests.

Read the source CSV/JSON the user points at, and for each column flagged as PII
(names, emails, phone numbers), replace values with realistic fake ones using a
local Faker script. Keep referential integrity (same input maps to same fake
output within the file).

Writes the anonymized copy next to the source. Everything runs locally; the real
data is only read to be scrubbed and is never sent anywhere.
