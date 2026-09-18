---
name: postgres-mcp
description: MCP server for read-only SQL queries and schema inspection.
---

# postgres MCP server

The reference PostgreSQL server. Read-only.

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://readonly@localhost:5432/app"]
    }
  }
}
```

It exposes a `query` tool that runs SELECT statements inside a read-only
transaction, plus schema-inspection resources. It connects only to the database
URL you configure and cannot write or delete data.
