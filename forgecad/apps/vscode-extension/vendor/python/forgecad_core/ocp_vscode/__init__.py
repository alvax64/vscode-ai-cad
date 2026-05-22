"""Compatibility shim for scripts migrating from OCP CAD Viewer.

ForgeCAD keeps the familiar Python display API names, but these functions
record display intent for the shared CAD service instead of posting directly to
a VS Code WebView.
"""

from forgecad_core.display import *  # noqa: F403
from .comms import get_port, is_pytest, set_port  # noqa: F401

try:
    __all__ = [*__all__, "get_port", "is_pytest", "set_port"]  # type: ignore[name-defined]
except NameError:
    __all__ = ["get_port", "is_pytest", "set_port"]
