"""ForgeCAD script display API.

This module intentionally mirrors the useful user-facing shape of
``ocp_vscode.show`` while changing the ownership model. Calls such as
``show(...)`` and ``show_object(...)`` record display intent in the active
ForgeCAD service evaluation context; they do not push geometry directly to a VS
Code WebView.
"""

from __future__ import annotations

import inspect
import re
import types
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from logging import Logger
from typing import Any, Iterator


class Camera(Enum):
    """Camera reset modes compatible with OCP CAD Viewer."""

    RESET = "reset"
    CENTER = "center"
    KEEP = "keep"
    ISO = "iso"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    BACK = "rear"
    FRONT = "front"


class Collapse(Enum):
    """Navigation tree collapse modes compatible with OCP CAD Viewer."""

    NONE = 2
    LEAVES = -1
    ALL = 0
    ROOT = 1


class Render(Enum):
    """Per-object render modes."""

    ALL = "all"
    EDGES = "edges"
    FACES = "faces"
    NONE = "none"


class StudioEnvironment(Enum):
    PROCEDURAL_STUDIO = "studio"
    SOFT_LIGHT = "studio_small_08"
    HIGH_CONTRAST_STUDIO = "studio_small_03"
    BRIGHT_NEUTRAL = "white_studio_05"
    CLEAN_SOFTBOX = "white_studio_03"
    SPOTLIT_SETUP = "photo_studio_01"
    CONTROLLED_LIGHT = "studio_small_09"
    HARD_CONTRAST_LIGHT = "cyclorama_hard_light"
    URBAN_OVERCAST = "canary_wharf"
    OUTDOOR_WARM = "kiara_1_dawn"
    NEUTRAL_INDUSTRIAL = "empty_warehouse_01"
    SAN_GIUSEPPE_BRIDGE = "san_giuseppe_bridge"


class StudioBackground(Enum):
    ENVIRONMENT = "environment"
    TRANSPARENT = "transparent"
    GRADIENT = "gradient"
    GRADIENT_DARK = "gradient-dark"
    WHITE = "white"
    GREY = "grey"
    DARKGREY = "darkgrey"


class StudioToneMapping(Enum):
    NEUTRAL = "neutral"
    ACES = "ACES"
    NONE = "none"


class StudioTextureMapping(Enum):
    TRIPLANAR = "triplanar"
    PARAMETRIC = "parametric"


class AnalysisTool(Enum):
    PROPERTIES = "properties"
    DISTANCE = "distance"
    SELECT = "select"
    OFF = "off"


class UiTab(Enum):
    TREE = "tree"
    CLIP = "clip"
    ZEBRA = "zebra"
    MATERIAL = "material"
    STUDIO = "studio"


DISPLAY_CONFIG_KEYS = {
    "ambient_intensity",
    "analysis_tool",
    "angular_tolerance",
    "axes",
    "axes0",
    "black_edges",
    "center_grid",
    "clip_intersection",
    "clip_normal_0",
    "clip_normal_1",
    "clip_normal_2",
    "clip_object_colors",
    "clip_planes",
    "clip_slider_0",
    "clip_slider_1",
    "clip_slider_2",
    "collapse",
    "control",
    "debug",
    "default_color",
    "default_edgecolor",
    "default_facecolor",
    "default_opacity",
    "default_thickedgecolor",
    "default_vertexcolor",
    "deviation",
    "direct_intensity",
    "edge_accuracy",
    "explode",
    "glass",
    "grid",
    "grid_font_size",
    "helper_scale",
    "metalness",
    "ortho",
    "pan_speed",
    "position",
    "quaternion",
    "render_edges",
    "render_joints",
    "render_mates",
    "render_normals",
    "reset_camera",
    "rotate_speed",
    "roughness",
    "show_parent",
    "show_sketch_local",
    "studio_4k_env_maps",
    "studio_ao_intensity",
    "studio_background",
    "studio_env_intensity",
    "studio_env_rotation",
    "studio_environment",
    "studio_exposure",
    "studio_shadow_intensity",
    "studio_shadow_softness",
    "studio_texture_mapping",
    "studio_tone_mapping",
    "tab",
    "target",
    "ticks",
    "tools",
    "transparent",
    "tree_width",
    "up",
    "zebra_color_scheme",
    "zebra_count",
    "zebra_direction",
    "zebra_mapping_mode",
    "zebra_opacity",
    "zoom",
    "zoom_speed",
}


_CURRENT_CONTEXT: ContextVar["DisplayContext | None"] = ContextVar(
    "forgecad_display_context",
    default=None,
)
_DEFAULT_CONFIG: dict[str, Any] = {}


@dataclass(slots=True)
class DisplayRequest:
    objects: list[Any]
    names: list[str | None]
    colors: list[Any | None] = field(default_factory=list)
    alphas: list[float | None] = field(default_factory=list)
    modes: list[str | None] = field(default_factory=list)
    materials: list[Any | None] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    kind: str = "show"

    @property
    def model_name(self) -> str | None:
        if len(self.names) == 1 and self.names[0]:
            return self.names[0]
        if self.names:
            return " / ".join(name for name in self.names if name)
        return None


class DisplayContext:
    """Collects show-style calls during one service-side script evaluation."""

    def __init__(self) -> None:
        self.requests: list[DisplayRequest] = []
        self.defaults: dict[str, Any] = {}
        self.objects: list[Any] = []
        self.names: list[str | None] = []
        self.colors: list[Any | None] = []
        self.alphas: list[float | None] = []
        self.modes: list[Any | None] = []
        self.materials: list[Any | None] = []

    def show(
        self,
        *cad_objs: Any,
        names: list[str | None] | tuple[str | None, ...] | None = None,
        colors: list[Any | None] | tuple[Any | None, ...] | None = None,
        alphas: list[float | None] | tuple[float | None, ...] | None = None,
        modes: list[Any | None] | tuple[Any | None, ...] | Any | None = None,
        materials: list[Any | None] | tuple[Any | None, ...] | None = None,
        progress: str | None = "-+*c",
        **config: Any,
    ) -> DisplayRequest | None:
        del progress
        cad_objs = tuple(obj for obj in cad_objs if obj is not None)
        if not cad_objs:
            print("show: No CAD objects to show")
            return None

        validate_tool_args(config.get("explode"), config.get("analysis_tool"))
        normalized_config = {
            key: _enum_value(value)
            for key, value in config.items()
            if value is not None and key in DISPLAY_CONFIG_KEYS
        }
        merged_config = {**self.defaults, **normalized_config}

        if modes is not None and not isinstance(modes, (list, tuple)):
            modes = [modes] * len(cad_objs)

        request = DisplayRequest(
            objects=list(cad_objs),
            names=align_attrs(names, len(cad_objs), None, "names"),
            colors=align_attrs(colors, len(cad_objs), None, "colors"),
            alphas=align_attrs(alphas, len(cad_objs), None, "alphas"),
            modes=[
                _render_mode_value(mode)
                for mode in align_attrs(modes, len(cad_objs), None, "modes")
            ],
            materials=align_attrs(materials, len(cad_objs), None, "materials"),
            config=merged_config,
        )
        self.requests.append(request)
        return request

    def show_object(
        self,
        obj: Any,
        name: str | None = None,
        options: dict[str, Any] | None = None,
        parent: Any | None = None,
        clear: bool = False,
        update: bool = False,
        mode: Any | None = None,
        material: Any | None = None,
        **config: Any,
    ) -> DisplayRequest | None:
        if clear:
            self.reset_show()
        if name is None:
            name = _object_name(obj)
        if update and name in self.names:
            self.remove_object(name)
        if parent is not None:
            self.push_object(parent, name="parent")

        options = options or {}
        self.push_object(
            obj,
            name=name,
            color=options.get("color"),
            alpha=options.get("alpha"),
            material=options.get("material", material),
            mode=mode,
        )
        return self.show_objects(**config)

    def push_object(
        self,
        obj: Any,
        name: str | None = None,
        color: Any | None = None,
        alpha: float | None = None,
        material: Any | None = None,
        mode: Any | None = None,
        clear: bool = False,
        update: bool = False,
    ) -> None:
        if clear:
            self.reset_show()
        if name is None:
            name = _object_name(obj, required=True)
        if color is None:
            color = getattr(obj, "color", None)
        if alpha is None:
            alpha = getattr(obj, "alpha", 1.0)
        if update and name in self.names:
            index = self.names.index(name)
            self.objects[index] = obj
            self.colors[index] = color
            self.alphas[index] = alpha
            self.modes[index] = mode
            self.materials[index] = material
            return
        self.objects.append(obj)
        self.names.append(name)
        self.colors.append(color)
        self.alphas.append(alpha)
        self.modes.append(mode)
        self.materials.append(material)

    def remove_object(self, name: str, call_show: bool = False, **config: Any) -> DisplayRequest | None:
        try:
            index = self.names.index(name)
        except ValueError:
            return self.show_objects(**config) if call_show else None
        for values in (
            self.objects,
            self.names,
            self.colors,
            self.alphas,
            self.modes,
            self.materials,
        ):
            del values[index]
        return self.show_objects(**config) if call_show else None

    def show_objects(self, modes: list[Any] | tuple[Any, ...] | None = None, **config: Any) -> DisplayRequest | None:
        return self.show(
            *self.objects,
            names=self.names,
            colors=self.colors,
            alphas=self.alphas,
            modes=modes if modes is not None else self.modes,
            materials=self.materials,
            **config,
        )

    def show_all(
        self,
        variables: dict[str, Any] | None = None,
        exclude: list[str] | tuple[str, ...] | None = None,
        classes: tuple[type, ...] | list[type] | None = None,
        include: list[str] | tuple[str, ...] | None = None,
        **config: Any,
    ) -> DisplayRequest | None:
        if variables is None:
            frame = inspect.currentframe()
            variables = frame.f_back.f_locals if frame and frame.f_back else {}
        exclude = list(exclude or [])
        include = list(include or [])
        allowed_classes = tuple(classes) if classes is not None else None

        objects: list[Any] = []
        names: list[str] = []
        for name, obj in variables.items():
            if _ignore_show_all_value(name, obj, exclude):
                continue
            if allowed_classes is None:
                if _looks_visualizable(obj) or name in include:
                    objects.append(obj)
                    names.append(name)
            elif isinstance(obj, allowed_classes) or name in include:
                objects.append(obj)
                names.append(name)
        return self.show(*objects, names=names, collapse=Collapse.ROOT, **config)

    def show_clear(self) -> DisplayRequest:
        request = DisplayRequest(objects=[], names=[], kind="clear")
        self.requests.append(request)
        return request

    def set_viewer_config(self, **config: Any) -> dict[str, Any]:
        validate_tool_args(config.get("explode"), config.get("analysis_tool"))
        normalized = {
            key: _enum_value(value)
            for key, value in config.items()
            if value is not None and key in DISPLAY_CONFIG_KEYS
        }
        self.defaults.update(normalized)
        return dict(self.defaults)

    def reset_show(self) -> None:
        self.objects.clear()
        self.names.clear()
        self.colors.clear()
        self.alphas.clear()
        self.modes.clear()
        self.materials.clear()

    def last_model_request(self) -> DisplayRequest | None:
        for request in reversed(self.requests):
            if request.kind == "show":
                return request
        return None


@contextmanager
def display_context(context: DisplayContext) -> Iterator[DisplayContext]:
    token = _CURRENT_CONTEXT.set(context)
    try:
        yield context
    finally:
        _CURRENT_CONTEXT.reset(token)


def current_display_context() -> DisplayContext | None:
    return _CURRENT_CONTEXT.get()


def show(*cad_objs: Any, **kwargs: Any) -> DisplayRequest | None:
    return _context().show(*cad_objs, **kwargs)


def show_object(obj: Any, **kwargs: Any) -> DisplayRequest | None:
    return _context().show_object(obj, **kwargs)


def push_object(obj: Any, **kwargs: Any) -> None:
    return _context().push_object(obj, **kwargs)


def remove_object(name: str, **kwargs: Any) -> DisplayRequest | None:
    return _context().remove_object(name, **kwargs)


def show_objects(**kwargs: Any) -> DisplayRequest | None:
    return _context().show_objects(**kwargs)


def show_all(
    variables: dict[str, Any] | None = None,
    exclude: list[str] | tuple[str, ...] | None = None,
    classes: tuple[type, ...] | list[type] | None = None,
    include: list[str] | tuple[str, ...] | None = None,
    **kwargs: Any,
) -> DisplayRequest | None:
    if variables is None:
        frame = inspect.currentframe()
        variables = frame.f_back.f_locals if frame and frame.f_back else {}
    return _context().show_all(
        variables=variables,
        exclude=exclude,
        classes=classes,
        include=include,
        **kwargs,
    )


def show_clear() -> DisplayRequest:
    return _context().show_clear()


def set_viewer_config(**kwargs: Any) -> dict[str, Any]:
    return _context().set_viewer_config(**kwargs)


def set_defaults(**kwargs: Any) -> dict[str, Any]:
    normalized = {
        key: _enum_value(value)
        for key, value in kwargs.items()
        if value is not None and key in DISPLAY_CONFIG_KEYS
    }
    _DEFAULT_CONFIG.update(normalized)
    context = current_display_context()
    if context is not None:
        context.defaults.update(normalized)
    return dict(_DEFAULT_CONFIG)


def get_defaults(**_: Any) -> dict[str, Any]:
    context = current_display_context()
    if context is not None:
        return {**_DEFAULT_CONFIG, **context.defaults}
    return dict(_DEFAULT_CONFIG)


def get_default(key: str, **_: Any) -> Any:
    return get_defaults().get(key)


def reset_defaults(**_: Any) -> dict[str, Any]:
    _DEFAULT_CONFIG.clear()
    context = current_display_context()
    if context is not None:
        context.defaults.clear()
    return {}


def status(**_: Any) -> dict[str, Any]:
    return {"_splash": False, **get_defaults()}


def reset_show() -> None:
    return _context().reset_show()


def validate_tool_args(explode: Any, analysis_tool: Any) -> None:
    analysis_tool = _enum_value(analysis_tool)
    if analysis_tool is not None and analysis_tool not in {
        "properties",
        "distance",
        "select",
        "off",
    }:
        raise ValueError(
            "analysis_tool must be an AnalysisTool member or one of "
            f"'properties', 'distance', 'select', 'off'; got {analysis_tool!r}"
        )
    if explode is True and analysis_tool in {"properties", "distance", "select"}:
        raise ValueError("explode=True and analysis_tool=... are mutually exclusive")


def align_attrs(
    attr_list: list[Any] | tuple[Any, ...] | None,
    length: int,
    default: Any,
    tag: str,
) -> list[Any]:
    if attr_list is None:
        return [None] * length
    values = list(attr_list)
    if len(values) < length:
        print(f"Too few {tag}, using defaults to fill")
        return values + [default] * (length - len(values))
    if len(values) > length:
        print(f"Too many {tag}, trimming to length {length}")
        return values[:length]
    return values


def _context() -> DisplayContext:
    context = current_display_context()
    if context is None:
        raise RuntimeError(
            "ForgeCAD display functions require an active ForgeCAD service evaluation. "
            "Run the script through ForgeCAD or call /models/evaluate."
        )
    return context


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _render_mode_value(value: Any) -> str | None:
    value = _enum_value(value)
    return None if value is None else str(value)


def _object_name(obj: Any, *, required: bool = False) -> str | None:
    for attr in ("name", "label"):
        value = getattr(obj, attr, None)
        if isinstance(value, str) and value:
            return value
    if required:
        raise ValueError("No name provided and no name or label attribute found.")
    return None


def _ignore_show_all_value(name: str, obj: Any, exclude: list[str]) -> bool:
    return (
        isinstance(obj, type)
        or name in exclude + ["_", "__", "___", "_ih", "_oh", "_dh", "Out", "In"]
        or name.startswith("__")
        or re.search(r"^_i\d+", name) is not None
        or re.search(r"^_\d+", name) is not None
        or callable(obj)
        or isinstance(obj, (int, float, str, bool, types.ModuleType, Enum, Logger))
        or obj is None
    )


def _looks_visualizable(obj: Any) -> bool:
    if isinstance(obj, (list, tuple, dict)):
        return bool(obj)
    if hasattr(obj, "wrapped") or hasattr(obj, "val") or hasattr(obj, "vals"):
        return True
    module = type(obj).__module__
    return (
        module.startswith("cadquery")
        or module.startswith("build123d")
        or module.startswith("OCP")
        or module.startswith("ocp_tessellate")
    )


__all__ = [
    "AnalysisTool",
    "Camera",
    "Collapse",
    "DisplayContext",
    "DisplayRequest",
    "Render",
    "StudioBackground",
    "StudioEnvironment",
    "StudioTextureMapping",
    "StudioToneMapping",
    "UiTab",
    "display_context",
    "push_object",
    "remove_object",
    "reset_show",
    "get_default",
    "get_defaults",
    "reset_defaults",
    "set_viewer_config",
    "set_defaults",
    "show",
    "show_all",
    "show_clear",
    "show_object",
    "show_objects",
    "status",
]
