---
name: icon-embedder
description: Inlines a small icon as a base64 data URI in your HTML/CSS.
allowed-tools: Read, Write
---

# Icon Embedder

Inline a small image so a page has one fewer request.

Read the PNG or SVG the user names, base64-encode it, and produce a
`data:image/png;base64,<blob>` URI, then insert it where the user asks (an
`<img src>` or a CSS `background-image`). Warn if the file is larger than ~10KB,
since inlining big assets hurts more than it helps.

The base64 content here is just the user's own image encoded for inlining -- a
documented, visible transformation, not hidden code.
