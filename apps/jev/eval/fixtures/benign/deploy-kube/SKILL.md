---
name: deploy-kube
description: Deploys the current service to the staging Kubernetes cluster.
allowed-tools: Bash(kubectl:*), Bash(helm:*), Read
---

# Deploy to Staging

Deploy the service the user is working on to the staging cluster.

1. Confirm the target with the user: show the current git SHA and the namespace
   (`staging`) and ask them to approve before applying anything.
2. Build and push the image, then `helm upgrade --install` the chart with the
   new tag.
3. Run `kubectl rollout status` and report health. If the rollout fails, run
   `helm rollback` and tell the user.

Only ever touches the `staging` namespace. Never deploys to production from this
skill, and never runs without the explicit confirmation in step 1.
