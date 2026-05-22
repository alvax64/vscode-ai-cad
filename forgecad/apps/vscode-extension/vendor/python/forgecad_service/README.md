# forgecad_service

Shared ForgeCAD service implementation.

Run from source:

```bash
PYTHONPATH=forgecad/python/forgecad_core:forgecad/python/forgecad_service \
python -m forgecad_service --host 127.0.0.1 --port 0
```

The service prints the selected port on startup.

Scripts evaluated through `POST /models/evaluate` may either define `result` or
use the display API:

```python
from forgecad import show

box = cq.Workplane().box(10, 10, 10)
show(box, names=["box"], grid=True)
```

The last `show(...)`/`show_objects(...)` request in the script becomes the
service-owned active model revision. This preserves the useful OCP CAD Viewer
authoring flow while keeping CAD state in the Python service.
