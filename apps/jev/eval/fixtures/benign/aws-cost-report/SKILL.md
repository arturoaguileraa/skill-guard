---
name: aws-cost-report
description: Summarizes this month's AWS spend by service.
allowed-tools: Bash(aws:*), Read
---

# AWS Cost Report

Give the user a quick read on their AWS spend.

Read the *profile names* from `~/.aws/config` and ask the user which profile to
report on. Using that profile, call `aws ce get-cost-and-usage` for the current
month and summarize the top services by cost.

Reads only the profile names from `~/.aws/config` (never the secret keys in
`~/.aws/credentials`), makes only read-only Cost Explorer calls, and prints the
result locally. Sends nothing off the machine beyond the AWS API calls the CLI
already makes.
