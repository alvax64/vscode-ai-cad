"""Reusable ForgeCAD domain primitives."""

from .errors import ErrorPayload, ForgeCADError
from .display import (
    AnalysisTool,
    Camera,
    Collapse,
    Render,
    StudioBackground,
    StudioEnvironment,
    StudioTextureMapping,
    StudioToneMapping,
    UiTab,
    push_object,
    remove_object,
    reset_show,
    set_viewer_config,
    show,
    show_all,
    show_clear,
    show_object,
    show_objects,
)
from .models import (
    ModelRecord,
    RevisionRecord,
    SessionRecord,
    ServiceEvent,
)
from .serialization import to_json_compatible

__all__ = [
    "ErrorPayload",
    "ForgeCADError",
    "AnalysisTool",
    "Camera",
    "Collapse",
    "ModelRecord",
    "Render",
    "RevisionRecord",
    "ServiceEvent",
    "SessionRecord",
    "StudioBackground",
    "StudioEnvironment",
    "StudioTextureMapping",
    "StudioToneMapping",
    "UiTab",
    "push_object",
    "remove_object",
    "reset_show",
    "set_viewer_config",
    "show",
    "show_all",
    "show_clear",
    "show_object",
    "show_objects",
    "to_json_compatible",
]
