# Phase 0 Record

Phase 0 establishes the new product frame and project boundaries. It does not
move runtime code yet.

## Completed In This Phase

- Chosen working product name: ForgeCAD.
- Added architecture docs for the product vision, shared CAD service, protocol,
  and model state.
- Added placeholder directories for future app, package, and Python service
  boundaries.
- Marked the existing OCP CAD Viewer implementation as legacy source material
  that will be migrated intentionally.

## New Top-Level Boundaries

```text
apps/vscode-extension
packages/mcp-server
packages/cad-service-client
packages/webview-renderer
python/forgecad_core
python/forgecad_service
examples/agent-workflows
docs/architecture
```

## Legacy Code To Mine First

- `ocp_vscode/show.py` for conversion and tessellation.
- `ocp_vscode/backend.py` for model shape mapping.
- `ocp_vscode/measure.py` for properties and distance.
- `resources/viewer.html` for renderer integration.
- `src/controller.ts` for existing VS Code to Python/WebView routing.

## Phase 1 Entry Criteria

- Service package skeleton exists.
- Public service API draft is documented.
- Model/session/revision vocabulary is stable enough to implement.
- Existing code migration targets are known.

## Phase 1 First Deliverable

The first real deliverable should be a Python service that can:

1. Start from the command line.
2. Create a session.
3. Evaluate or accept a simple model.
4. Produce metadata.
5. Produce a tessellated scene payload.
6. Export STL.
