---
name: kubectl-mcp
description: MCP server for read-mostly Kubernetes operations against a context.
---

# kubectl MCP server

An MCP server that wraps `kubectl` for a chosen context.

```json
{
  "mcpServers": {
    "kubectl": {
      "command": "npx",
      "args": ["-y", "kubectl-mcp-server", "--context", "staging", "--read-only"]
    }
  }
}
```

Tools: `get`, `describe`, `logs`, and (behind a confirm flag) `apply`. It is
pinned to the `staging` context passed on the command line and starts in
`--read-only` mode; mutating calls require the operator to opt in per action.
