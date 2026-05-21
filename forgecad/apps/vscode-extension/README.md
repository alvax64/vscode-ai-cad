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

Use this exact flow when running the extension from source:

1. Open the extension folder itself in VS Code:

   ```bash
   code /home/alvax/yo/vscode-ai-cad/forgecad/apps/vscode-extension
   ```

2. Install dependencies once:

   ```bash
   npm install
   ```

3. Press `F5`, or open **Run and Debug** and choose
   **Run ForgeCAD Extension**. This uses `.vscode/launch.json`, runs
   `npm: compile`, and opens a new isolated **Extension Development Host**
   window with a separate user-data directory and extension directory.

4. In the Extension Development Host, open a normal workspace folder, then trust
   it when VS Code asks. Local service startup is blocked in untrusted
   workspaces.

5. Select the Python executable used to start the ForgeCAD service. This does
   not require the Microsoft Python extension:

   ```text
   ForgeCAD: Select Python Interpreter
   ```

   The command writes `forgecad.python.path` into the demo workspace settings.

6. If you also want VS Code's own `Python: Select Interpreter` command, install
   the Microsoft Python extension inside the Extension Development Host:

   - Open Extensions in the Extension Development Host.
   - Install `Python` by Microsoft (`ms-python.python`).
   - Run `Python: Select Interpreter`.

   This install is isolated under `.vscode-test/extensions`; it does not load
   your normal user extensions.

7. Open the Command Palette in the Extension Development Host and run:

   ```text
   ForgeCAD: Start CAD Service
   ForgeCAD: Open Viewer
   ```

   You can also click the ForgeCAD activity-bar icon. The **Service** view has
   title-bar buttons for starting the service, opening the viewer, and
   refreshing status.

If the development host prints errors from unrelated extensions such as
`vscodevim`, `vscode-custom-css`, or Claude integrations, make sure you launched
with **Run ForgeCAD Extension** from this folder. The checked-in launch config
passes `--user-data-dir` and `--extensions-dir` so your normal installed
extensions do not load in the ForgeCAD development host. Extensions you install
inside the development host, such as Microsoft Python, are kept in that isolated
test extension directory.

In development, the extension can resolve assets from the monorepo layout:

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
python3 -m forgecad_service --host 127.0.0.1 --port 0 --quiet --auth-token <random-token>
```

For VSIX/package builds, run:

```bash
npm install
npm run package-assets
npm run compile
```

`package-assets` copies the Python service/core packages and WebView renderer
under `vendor/`, so the installed extension does not depend on sibling
monorepo folders.

Set `forgecad.service.url` and `forgecad.service.token` to use an already-running
service instead.
