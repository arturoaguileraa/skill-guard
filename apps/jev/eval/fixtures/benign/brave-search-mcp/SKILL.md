---
name: brave-search-mcp
description: MCP server for web and local search via the Brave Search API.
---

# brave-search MCP server

The official Brave Search MCP server. Add it to your MCP config:

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@brave/brave-search-mcp-server"],
      "env": { "BRAVE_API_KEY": "${BRAVE_API_KEY}" }
    }
  }
}
```

It exposes `brave_web_search` and `brave_local_search`. Each tool takes a query
and returns public search results from `https://api.search.brave.com`. It only
calls the Brave Search API with the query you pass; it reads no local files and
sends nothing but the search query.
