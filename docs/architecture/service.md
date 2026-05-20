# Shared CAD Service

The shared CAD service is the center of ForgeCAD. It owns CAD sessions, model
revisions, BRep objects, tessellation outputs, model metadata, measurements,
and exports.

## Responsibilities

- Start and manage workspace CAD sessions.
- Evaluate or load model sources.
- Store canonical model and revision state.
- Keep BRep objects available for inspection and export.
- Generate tessellated scene payloads for renderers.
- Provide structured metadata and topology queries.
- Measure distances and angles between referenced shapes.
- Export STL files first, then support additional formats later.
- Publish model and revision lifecycle events.

## First Implementation Shape

The first service should be a Python HTTP plus WebSocket service in
`python/forgecad_service`.

Python is the right first owner because the current codebase already depends on
OCP, CadQuery, build123d, `ocp_tessellate`, and the existing measurement code.
TypeScript remains important for the VS Code extension, MCP adapter, and
browser renderer, but it should not become the geometry runtime.

## Internal Modules

Suggested package layout:

```text
python/forgecad_service/
  README.md
  forgecad_service/
    __init__.py
    server.py
    settings.py
    sessions.py
    model_store.py
    runtime.py
    tessellation.py
    inspection.py
    measurement.py
    export.py
    events.py
    errors.py
```

Reusable geometry helpers that should not depend on the HTTP service belong in
`python/forgecad_core`.

## Initial API Surface

- `GET /health`
- `POST /sessions`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/current`
- `POST /models/evaluate`
- `GET /models/{model_id}/revisions/{revision_id}`
- `GET /models/{model_id}/revisions/{revision_id}/tree`
- `GET /models/{model_id}/revisions/{revision_id}/metadata`
- `POST /models/{model_id}/revisions/{revision_id}/inspect`
- `POST /models/{model_id}/revisions/{revision_id}/measure`
- `POST /models/{model_id}/revisions/{revision_id}/export/stl`
- `POST /models/{model_id}/revisions/{revision_id}/tessellate`
- `WS /events`

Render capture can begin as a service request that delegates to an attached
renderer. Headless rendering can later satisfy the same request without VS Code.

## Migration Sources From The Current Codebase

- Tessellation and object conversion: `ocp_vscode/show.py`.
- Viewer state and config concepts: `ocp_vscode/config.py`.
- Shape mapping and BRep lookup: `ocp_vscode/backend.py`.
- Distance and properties: `ocp_vscode/measure.py`.
- Standalone service precedent: `ocp_vscode/standalone.py`.

The first migration should copy behavior behind new APIs. It should not rename
the original modules in-place until tests cover the new service behavior.
