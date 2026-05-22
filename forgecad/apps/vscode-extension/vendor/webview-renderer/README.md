# ForgeCAD WebView Renderer

This package is the Phase 2 service-driven renderer client. It does not own CAD
models or revisions. It attaches to a ForgeCAD service session, asks the service
for the active revision tessellation, renders that revision, listens for
`view.command` events, and reports renderer-owned state back to the service.

## Runtime Contract

The renderer is authored in TypeScript under `src/` and emitted to `dist/`.
The VS Code extension and standalone HTML entrypoint load the compiled
`dist/forgecad-renderer-client.js` module.

```bash
npm install
npm run compile
```

Open `public/index.html` with these query parameters:

```text
?service=http://127.0.0.1:PORT&session=session_000001
```

The client will:

- `POST /renderers` to attach itself to the session.
- `GET /sessions/{id}/current` to resolve the active service-owned model.
- `POST /models/{model}/revisions/{revision}/tessellate` to fetch scene data.
- Connect to `WS /events` and handle `revision.created` and `view.command`.
- `POST /renderers/{id}/view-state` when camera, selection, visibility, or
  clipping state changes.
- `POST /renderers/{id}/captures` when a capture command completes.

## Adapter API

`ForgeCADRendererClient` accepts an adapter object so the same client can host
the legacy `three-cad-viewer` WebView today and a headless Playwright page
later.

```ts
const adapter = {
  renderRevision({ modelId, revisionId, tessellatedScene, config }) {},
  captureView(config) {},
  captureOverview(views, config) {},
  setCamera(camera) {},
  setVisibility(visibleNodeStates) {},
  setClipping(clipping) {},
  getViewState() {},
  onViewStateChanged(callback) {}
};
```

The bundled `DomStatusRenderer` is a dependency-free fallback for contract
testing. Production VS Code and headless rendering use the exported
`createThreeCadViewerAdapter`, backed by `three-cad-viewer`.
