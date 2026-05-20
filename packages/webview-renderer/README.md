# ForgeCAD WebView Renderer

This package is reserved for the shared browser renderer.

The renderer should be hostable in:

- A VS Code WebView.
- A headless browser page for capture.
- A future standalone browser shell.

## Responsibilities

- Render tessellated scene payloads from the shared CAD service.
- Preserve useful `three-cad-viewer` capabilities.
- Support request/response commands for captures and view changes.
- Report selection, camera, clipping, and visibility state.

The renderer owns view state only. It does not own canonical model state.
