# ForgeCAD MCP Server

This package is reserved for the generic ForgeCAD MCP server.

It must be usable by any MCP-aware agent, including agents running outside VS
Code. VS Code can register it, but it should not require VS Code APIs.

## Responsibilities

- Expose ForgeCAD tools, resources, and prompts through MCP.
- Connect to the shared CAD service through `@forgecad/cad-service-client`.
- Resolve current model and revision through the service.
- Return agent-friendly text, JSON, and image content.

## Initial Tool Set

- `cad_status`
- `cad_get_current_model`
- `cad_get_scene_tree`
- `cad_inspect_model`
- `cad_capture_view`
- `cad_capture_overview`
- `cad_export_stl`

Mutating viewer tools such as camera, visibility, and clipping should follow
after the read-only loop is stable.
