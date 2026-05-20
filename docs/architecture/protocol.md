# Protocol And API Boundaries

ForgeCAD has three external client classes:

- Generic MCP clients.
- VS Code extension and WebView renderer.
- Future CLI, headless renderer, or desktop clients.

All clients communicate through the shared CAD service or a typed adapter over
that service.

## Boundary Rules

- MCP does not own CAD state.
- VS Code does not own CAD state.
- The WebView does not own CAD state.
- The CAD service owns model state, BRep state, revisions, metadata, and export
  state.
- Renderers own transient view state: camera, viewport dimensions, selected
  objects, local visibility, clipping display, and temporary screenshot setup.

## Service Protocol

Use HTTP for request/response operations and WebSocket for events.

HTTP is simple to call from TypeScript, Python, tests, MCP adapters, and future
tools. WebSocket events are needed so the renderer and extension can react when
models, revisions, exports, or errors change.

## MCP Adapter

The MCP server in `packages/mcp-server` should be a generic adapter:

```text
MCP client
  -> @forgecad/mcp-server
      -> @forgecad/cad-service-client
          -> ForgeCAD service
```

It must be runnable without VS Code. VS Code can still register it through an
MCP server definition provider when the extension is installed.

## Renderer Adapter

The renderer package should support two hosts:

- VS Code WebView.
- Headless browser page, initially through Playwright or another browser host.

Both hosts should speak the same renderer command protocol:

- `render_revision`
- `capture_view`
- `capture_overview`
- `set_camera`
- `set_visibility`
- `set_clipping`
- `get_view_state`

## Event Types

Initial service events:

- `session.created`
- `session.current_changed`
- `model.created`
- `model.deleted`
- `revision.created`
- `revision.metadata_ready`
- `revision.tessellation_ready`
- `export.created`
- `renderer.attached`
- `renderer.detached`
- `error`

Every event should carry:

- `event_id`
- `event_type`
- `session_id`
- `model_id`, when applicable
- `revision_id`, when applicable
- `created_at`

## Error Shape

All service errors should use a stable shape:

```json
{
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "Model was not found",
    "details": {},
    "recoverable": true
  }
}
```

Agents need predictable errors so they can recover without guessing.
