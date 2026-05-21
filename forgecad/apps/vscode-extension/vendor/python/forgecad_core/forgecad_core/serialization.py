"""Helpers for keeping ForgeCAD API payloads JSON-compatible."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any


def to_json_compatible(value: Any) -> Any:
    """Recursively convert common CAD/numeric payload objects for json.dumps.

    The tessellation stack can return NumPy arrays and scalar values. ForgeCAD
    should expose plain JSON structures at its API boundary instead of leaking
    those implementation-specific container types to clients.
    """

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if is_dataclass(value) and not isinstance(value, type):
        return to_json_compatible(asdict(value))
    if isinstance(value, Mapping):
        return {
            _json_key(key): to_json_compatible(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_json_compatible(item) for item in value]

    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return to_json_compatible(tolist())

    if _is_opencascade_object(value):
        return _opencascade_object(value)

    item = getattr(value, "item", None)
    if callable(item):
        try:
            item_value = item()
        except ValueError:
            pass
        else:
            if item_value is not value:
                return to_json_compatible(item_value)

    return value


def _json_key(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    return str(to_json_compatible(value))


def _is_opencascade_object(value: Any) -> bool:
    module = type(value).__module__
    return module == "OCP" or module.startswith("OCP.")


def _opencascade_object(value: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": type(value).__name__,
        "module": type(value).__module__,
    }
    if hasattr(value, "Transformation"):
        data["is_identity"] = _call_bool(value, "IsIdentity")
        transformation = _call(value, "Transformation")
        if transformation is not None:
            data["transformation"] = _transformation_data(transformation)
        return data

    shape_type = _call(value, "ShapeType")
    if shape_type is not None:
        data["shape_type"] = str(shape_type).split(".")[-1]
    is_null = _call_bool(value, "IsNull")
    if is_null is not None:
        data["is_null"] = is_null
    hash_code = _call(value, "HashCode")
    if isinstance(hash_code, int):
        data["hash_code"] = hash_code
    return data


def _transformation_data(value: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": type(value).__name__,
    }
    matrix = _transformation_matrix(value)
    if matrix is not None:
        data["matrix"] = matrix
    form = _call(value, "Form")
    if form is not None:
        data["form"] = str(form).split(".")[-1]
    scale = _call(value, "ScaleFactor")
    if scale is not None:
        data["scale_factor"] = to_json_compatible(scale)
    translation = _call(value, "TranslationPart")
    if translation is not None:
        data["translation"] = _xyz(translation)
    return data


def _transformation_matrix(value: Any) -> list[list[float]] | None:
    if not hasattr(value, "Value"):
        return None
    try:
        return [
            [float(value.Value(row, column)) for column in range(1, 5)]
            for row in range(1, 4)
        ]
    except Exception:
        return None


def _xyz(value: Any) -> list[float] | None:
    try:
        return [float(value.X()), float(value.Y()), float(value.Z())]
    except Exception:
        return None


def _call(value: Any, name: str) -> Any:
    attr = getattr(value, name, None)
    if not callable(attr):
        return None
    try:
        return attr()
    except Exception:
        return None


def _call_bool(value: Any, name: str) -> bool | None:
    result = _call(value, name)
    return result if isinstance(result, bool) else None
