# ForgeCAD VS Code Extension

This directory is reserved for the new ForgeCAD VS Code application shell.

The current extension implementation still lives in the repository root under
`src/`. During later phases, the useful parts of that implementation should be
migrated here behind the shared CAD service architecture.

## Responsibilities

- Start or discover the shared CAD service.
- Host the interactive CAD WebView.
- Register the ForgeCAD MCP server with VS Code when available.
- Show service, session, model, and renderer status.
- Provide VS Code commands for opening the viewer, selecting a session, and
  exporting STL.

The extension should not own BRep geometry, model revisions, or export logic.
