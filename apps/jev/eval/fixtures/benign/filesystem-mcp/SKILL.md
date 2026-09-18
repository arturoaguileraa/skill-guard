---
name: filesystem-mcp
description: MCP server for scoped, read/write file operations in allowed dirs.
---

# filesystem MCP server

The reference filesystem server. It is scoped to the directories you pass as
arguments and refuses paths outside them.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]
    }
  }
}
```

Tools: `read_file`, `write_file`, `list_directory`, `move_file`,
`search_files`. Every operation is confined to the allowed roots given on the
command line; access outside them is denied. No network access at all.
