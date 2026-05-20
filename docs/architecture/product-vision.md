# ForgeCAD Product Vision

ForgeCAD is an agent-ready CAD environment built around a shared geometry
service. It uses the useful parts of OCP CAD Viewer and McpCAD, but it should
be treated as a new product.

## Goals

- Give agents a reliable way to create, inspect, render, debug, and export CAD
  models.
- Keep VS Code as the primary interactive shell without making VS Code the
  owner of model state.
- Support generic MCP clients outside VS Code.
- Preserve the strong OCP CAD Viewer path for CadQuery, build123d, OCP shapes,
  tessellation, and interactive 3D viewing.
- Reuse McpCAD's best product ideas: agent-first MCP tools, multi-view
  screenshots, explicit model metadata, checkpoint-style debugging, and a live
  renderer request bridge.

## Non-Goals For The Initial Product

- Maintain compatibility with the original OCP CAD Viewer user experience.
- Keep all legacy command names or settings.
- Make the MCP server depend on VS Code.
- Expose arbitrary script execution before there is a clear security model.
- Support every export format immediately. STL comes first.

## Product Principles

- The shared CAD service is the source of truth.
- Every model-changing operation creates a new revision.
- Every agent-visible output should include `session_id`, `model_id`, and
  `revision_id`.
- Renderers are clients. They do not own geometry.
- MCP tools should be flat, explicit, and safe by default.
- Agents may change the live viewer state when it is relevant, such as camera,
  visibility, clipping, or selection-oriented workflows.
- Headless rendering should use the same rendering package as the VS Code
  WebView where practical.

## Working Names

- Product: ForgeCAD.
- Python geometry package: `forgecad_core`.
- Python service package: `forgecad_service`.
- MCP package: `@forgecad/mcp-server`.
- TypeScript service client: `@forgecad/cad-service-client`.
- Web renderer package: `@forgecad/webview-renderer`.
- VS Code app package: `forgecad-vscode`.

These names are working names. They are intentionally documented before source
renames so later code changes can be made consistently.
