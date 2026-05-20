# ForgeCAD Architecture

ForgeCAD is the working product name for this fork. The product direction is no
longer "OCP CAD Viewer plus integrations"; it is a service-centered CAD IDE
foundation for VS Code and MCP-aware agents.

The architecture starts from a shared CAD service. VS Code, MCP clients,
renderers, and command-line tools are clients of that service.

## Documents

- [Product vision](./product-vision.md)
- [Shared CAD service](./service.md)
- [Protocol and API boundaries](./protocol.md)
- [Model state](./model-state.md)
- [Phase 0 record](./phase-0.md)

## Phase 0 Decisions

- Working product name: ForgeCAD.
- CAD state owner: `python/forgecad_service`.
- Reusable geometry core: `python/forgecad_core`.
- Generic MCP adapter: `packages/mcp-server`.
- VS Code app shell: `apps/vscode-extension`.
- Renderer package: `packages/webview-renderer`.
- TypeScript service client: `packages/cad-service-client`.

The existing OCP CAD Viewer files remain in place during Phase 0 so that later
phases can migrate working behavior intentionally instead of losing useful
viewer, tessellation, and measurement code.
