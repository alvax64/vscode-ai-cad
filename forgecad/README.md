# ForgeCAD Phase 1 Workspace

This directory contains the new ForgeCAD implementation. It is intentionally
separate from the legacy OCP CAD Viewer fork at the repository root.

Phase 1 focuses on the shared CAD service:

- Workspace sessions.
- Canonical model and revision state.
- Script evaluation hooks for CadQuery/build123d/OCP environments.
- Accepted model records for dependency-free API work.
- Metadata, scene tree, tessellation, and STL export API boundaries.
- A minimal HTTP service that can be called by future VS Code and MCP clients.

The service is designed to degrade cleanly when CAD dependencies are not
installed. In that case, session and accepted-model APIs still work, while
geometry operations return structured dependency errors.

## Layout

```text
forgecad/
  python/
    forgecad_core/
    forgecad_service/
  tests/
```

`forgecad_core` is for reusable geometry/domain types. `forgecad_service` owns
sessions, models, revisions, and service APIs.

## Phase 1 HTTP API

The Phase 1 service intentionally uses a small standard-library HTTP server so
the contract can be exercised before the MCP and VS Code adapters exist.

```text
GET  /health
GET  /events
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
POST /models/{model_id}/revisions/{revision_id}/export/stl
```

`/models/accept` exists for dependency-free adapter work. `/models/evaluate`,
`/tessellate`, and `/export/stl` require the runtime environment to provide the
CAD stack reported by `/health`.

## Local Verification

```bash
python -m unittest discover -s forgecad/tests -p 'test_*.py' -v
PYTHONPATH=forgecad/python/forgecad_core:forgecad/python/forgecad_service python -m forgecad_service --help
```
