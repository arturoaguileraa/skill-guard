---
name: terraform-planner
description: Runs terraform plan and explains the proposed infra changes.
allowed-tools: Bash(terraform:*), Read
---

# Terraform Planner

Show the user what a Terraform change would do before they apply it.

Run `terraform plan -out=tfplan` in the module the user names, then walk through
each resource being created, changed, or destroyed in plain language, calling
out anything destructive (deletes, replacements) prominently.

Only ever runs `plan`, never `apply` or `destroy` -- applying is the user's
decision and this skill stops at the plan. Reads state read-only.
