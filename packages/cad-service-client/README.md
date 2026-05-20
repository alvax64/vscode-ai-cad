# ForgeCAD CAD Service Client

This package is reserved for the TypeScript client used by the MCP server, VS
Code extension, and renderer host code.

## Responsibilities

- Provide typed wrappers around the shared CAD service HTTP API.
- Provide a typed WebSocket event client.
- Normalize errors into stable TypeScript types.
- Keep MCP and VS Code code from duplicating protocol details.

This package should not contain VS Code imports.
