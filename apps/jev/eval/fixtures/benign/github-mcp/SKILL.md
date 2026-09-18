---
name: github-mcp
description: MCP server for GitHub repo, issue, and PR operations.
---

# github MCP server

The official GitHub MCP server. Uses a personal access token you provide.

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" }
    }
  }
}
```

Tools cover reading repos, creating issues and PRs, and searching code, all
against `https://api.github.com` with your token. The token is used only to
authenticate to GitHub's own API; it is never sent anywhere else.
