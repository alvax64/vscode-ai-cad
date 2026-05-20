# ForgeCAD VS Code Extension

This is the Phase 3 VS Code client for ForgeCAD. It coordinates the shared CAD
service and hosts the browser renderer; it does not own CAD models, geometry,
metadata, revisions, tessellation, or exports.

## Responsibilities

- Start or connect to a ForgeCAD service.
- Create a workspace session and track the session id.
- Host the service-driven WebView renderer.
- Show service/session/model status.
- Export the active service-owned revision as STL.
- Copy the service/session endpoint for MCP clients.

## Development

Open this folder as a VS Code extension project or run an extension host with
`forgecad/apps/vscode-extension` as the extension root. The extension expects
the monorepo layout:

```text
forgecad/
  apps/vscode-extension
  packages/webview-renderer
  python/forgecad_core
  python/forgecad_service
```

The local service launcher sets `PYTHONPATH` to the two Python package folders
above and runs:

```bash
python3 -m forgecad_service --host 127.0.0.1 --port 0 --quiet
```

Set `forgecad.service.url` to use an already-running service instead.
