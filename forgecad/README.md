# ForgeCAD Workspace

This directory contains the new ForgeCAD implementation. It is intentionally
separate from the legacy OCP CAD Viewer fork at the repository root.

Phase 1 established the shared CAD service:

- Workspace sessions.
- Canonical model and revision state.
- Script evaluation hooks for CadQuery/build123d/OCP environments.
- Accepted model records for dependency-free API work.
- Metadata, scene tree, tessellation, and STL export API boundaries.
- A minimal HTTP service that can be called by future VS Code and MCP clients.

Phase 2 adds a service-driven renderer client boundary:

- Renderers attach to a workspace session with `POST /renderers`.
- The service remains the owner of models, revisions, BRep handles, and cached
  tessellation.
- Renderers own camera, selection, visibility, clipping, active tool, and
  viewport state.
- Render commands are queued as `view.command` service events over `WS /events`.
- Renderers report view state and captures back to the service.

The service is designed to degrade cleanly when CAD dependencies are not
installed. In that case, session and accepted-model APIs still work, while
geometry operations return structured dependency errors.

## Layout

```text
forgecad/
  python/
    forgecad_core/
    forgecad_service/
  packages/
    cad-service-client/
    webview-renderer/
  tests/
```

`forgecad_core` is for reusable geometry/domain types. `forgecad_service` owns
sessions, models, revisions, and service APIs.

## HTTP API

The service intentionally uses a small standard-library HTTP server so
the contract can be exercised before the MCP and VS Code adapters exist.

```text
GET  /health
GET  /events
WS   /events
GET  /sessions
POST /sessions
GET  /sessions/{session_id}
GET  /sessions/{session_id}/current
POST /models/accept
POST /models/evaluate
GET  /models/{model_id}/revisions/{revision_id}
GET  /models/{model_id}/revisions/{revision_id}/tree
GET  /models/{model_id}/revisions/{revision_id}/metadata
POST /models/{model_id}/revisions/{revision_id}/tessellate
POST /models/{model_id}/revisions/{revision_id}/inspect
POST /models/{model_id}/revisions/{revision_id}/measure
POST /models/{model_id}/revisions/{revision_id}/export/stl

GET  /renderers
POST /renderers
GET  /renderers/{renderer_id}
GET  /renderers/{renderer_id}/view-state
POST /renderers/{renderer_id}/view-state
POST /renderers/{renderer_id}/captures
GET  /render/commands/{command_id}
POST /render/render_revision
POST /render/capture
POST /render/capture_overview
POST /render/set_camera
POST /render/set_visibility
POST /render/set_clipping
POST /render/get_view_state
```

`/models/accept` exists for dependency-free adapter work. `/models/evaluate`,
`/tessellate`, and `/export/stl` require the runtime environment to provide the
CAD stack reported by `/health`.

The Phase 1 measurement endpoint supports dependency-free bounding-box,
point-distance, and vector-angle measurements. Shape-property and shape-distance
measurements use the BRep handle when one exists.

The Phase 2 render endpoints do not make the renderer canonical. They enqueue
commands for attached renderer clients and persist renderer-owned state so MCP,
VS Code, and headless rendering can share one service contract.

## Renderer Client

`packages/webview-renderer` contains a browser client that can be hosted in VS
Code WebViews, a standalone browser page, or a future Playwright headless
capture worker.

```text
forgecad/packages/webview-renderer/public/index.html?service=http://127.0.0.1:PORT&session=session_000001
```

The fallback DOM renderer is dependency-free and only validates the protocol.
Production VS Code integration should provide an adapter backed by
`three-cad-viewer`.

## Local Verification

```bash
python -m unittest discover -s forgecad/tests -p 'test_*.py' -v
PYTHONPATH=forgecad/python/forgecad_core:forgecad/python/forgecad_service python -m forgecad_service --help
```
