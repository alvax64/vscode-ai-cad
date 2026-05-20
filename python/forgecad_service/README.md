# forgecad_service

This package is reserved for the shared ForgeCAD service.

The service owns sessions, models, revisions, BRep object handles,
tessellation cache, inspection, measurement, and exports.

## First Service Capabilities

- Start from the command line.
- Create and list sessions.
- Track the active model and active revision.
- Evaluate or accept simple CAD models.
- Return metadata and scene trees.
- Produce tessellated scene payloads for renderers.
- Export STL.
- Publish events over WebSocket.

The service is the foundation for VS Code integration, MCP integration, and
headless rendering.
