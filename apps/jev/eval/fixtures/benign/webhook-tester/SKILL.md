---
name: webhook-tester
description: Sends sample events to your webhook endpoint to test handling.
allowed-tools: Bash(curl:*), Read
---

# Webhook Tester

Help the user test their own webhook receiver.

Read the target URL from `webhook.test.json` (the user's own endpoint, often a
`localhost` tunnel). For each sample event in the fixtures folder, POST it with
`curl` and show the response status and body so the user can verify their
handler.

Posts only the sample fixtures to the endpoint the user configured. Contains no
real data and no destination other than the one in the user's config.
