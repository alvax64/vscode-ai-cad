# forgecad_core

Reusable Python domain and geometry helpers for ForgeCAD.

This package should stay independent from HTTP, MCP, and VS Code.

## Display API

`forgecad_core.display` provides the ForgeCAD-native script display API:

```python
from forgecad import Camera, Render, show

show(part, names=["bracket"], modes=[Render.ALL], reset_camera=Camera.KEEP)
```

The API intentionally keeps the familiar OCP CAD Viewer names (`show`,
`show_object`, `push_object`, `show_objects`, `show_all`, `set_viewer_config`)
but records display intent for the shared ForgeCAD service. It does not send
geometry directly to a VS Code WebView.

For migration, the service evaluation runtime also supports common compatibility
imports such as:

```python
from ocp_vscode import show
from ocp_vscode.config import Render
from ocp_vscode.show import show_object
```
