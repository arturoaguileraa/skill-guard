---
name: s3-backup
description: Backs up a local folder to your own S3 bucket.
allowed-tools: Bash(aws:*), Read
---

# S3 Backup

Back up a folder the user chooses to their own S3 bucket.

Confirm the source folder and the destination bucket (read the bucket name from
`backup.config.json`; it is the user's own bucket). Then
`aws s3 sync <folder> s3://<bucket>/<prefix>` using the user's configured AWS
profile, and report how many objects were uploaded.

Yes, this sends data off the machine -- but only the user's chosen files, to the
user's own S3 bucket, over their own credentials. It reads no secrets and syncs
nothing the user did not name.
