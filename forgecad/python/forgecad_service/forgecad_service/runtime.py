"""Geometry runtime for ForgeCAD Phase 1."""

from __future__ import annotations

import importlib
import importlib.util
import os
import traceback
from dataclasses import dataclass
from typing import Any

from forgecad_core.errors import ForgeCADError


@dataclass(slots=True)
class EvaluationResult:
    name: str
    handle: Any
    metadata: dict[str, Any]
    scene_tree: dict[str, Any]
    tessellated_scene: dict[str, Any] | None
    warnings: list[str]


class GeometryRuntime:
    """CAD dependency adapter.

    The service shell is usable without CAD libraries. Real geometry operations
    require the environment to provide CadQuery/build123d/OCP and the legacy
    tessellation stack while we migrate the implementation.
    """

    def dependency_status(self) -> dict[str, bool]:
        return {
            name: self._can_import(name)
            for name in ("cadquery", "build123d", "OCP", "ocp_tessellate")
        }

    def evaluate_script(
        self,
        script: str,
        *,
        name: str = "result",
        include_tessellation: bool = True,
    ) -> EvaluationResult:
        cq = self._optional_import("cadquery")
        if cq is None:
            raise self._dependency_error("cadquery")

        namespace: dict[str, Any] = {
            "cq": cq,
            "cadquery": cq,
            "__name__": "__forgecad_script__",
        }

        build123d = self._optional_import("build123d")
        if build123d is not None:
            namespace["bd"] = build123d
            namespace["build123d"] = build123d

        try:
            exec(script, namespace)  # pylint: disable=exec-used
        except Exception as exc:
            raise ForgeCADError(
                "EVALUATION_FAILED",
                str(exc),
                details={"traceback": traceback.format_exc()},
                recoverable=True,
            ) from exc

        if "result" not in namespace:
            raise ForgeCADError(
                "RESULT_MISSING",
                "CAD script must define a variable named 'result'",
                recoverable=True,
            )

        result = namespace["result"]
        metadata = self.compute_metadata(result)
        scene_tree = self.build_scene_tree(result, name=name)
        tessellated_scene = (
            self.tessellate(result) if include_tessellation else None
        )
        return EvaluationResult(
            name=name,
            handle=result,
            metadata=metadata,
            scene_tree=scene_tree,
            tessellated_scene=tessellated_scene,
            warnings=[],
        )

    def compute_metadata(self, obj: Any) -> dict[str, Any]:
        shape = self._shape_from_object(obj)
        metadata: dict[str, Any] = {
            "volume": None,
            "surface_area": None,
            "bounding_box": None,
            "face_count": None,
            "edge_count": None,
            "solid_count": None,
            "shell_count": None,
            "is_valid": None,
        }
        if shape is None:
            return metadata

        for method, key in (
            ("Volume", "volume"),
            ("Area", "surface_area"),
        ):
            try:
                metadata[key] = round(float(getattr(shape, method)()), 6)
            except Exception:
                pass

        try:
            bb = shape.BoundingBox()
            metadata["bounding_box"] = {
                "min": [round(bb.xmin, 6), round(bb.ymin, 6), round(bb.zmin, 6)],
                "max": [round(bb.xmax, 6), round(bb.ymax, 6), round(bb.zmax, 6)],
                "extents": [
                    round(bb.xmax - bb.xmin, 6),
                    round(bb.ymax - bb.ymin, 6),
                    round(bb.zmax - bb.zmin, 6),
                ],
            }
        except Exception:
            pass

        for method, key in (
            ("Faces", "face_count"),
            ("Edges", "edge_count"),
            ("Solids", "solid_count"),
            ("Shells", "shell_count"),
        ):
            try:
                metadata[key] = len(getattr(shape, method)())
            except Exception:
                pass

        try:
            from OCP.BRepCheck import BRepCheck_Analyzer

            metadata["is_valid"] = bool(BRepCheck_Analyzer(shape.wrapped).IsValid())
        except Exception:
            pass

        return metadata

    def build_scene_tree(self, obj: Any, *, name: str = "result") -> dict[str, Any]:
        cq = self._optional_import("cadquery")
        if cq is not None and isinstance(obj, cq.Assembly):
            return self._assembly_tree(obj)
        return {
            "id": "/result",
            "name": name,
            "type": type(obj).__name__,
            "children": [],
        }

    def tessellate(self, obj: Any) -> dict[str, Any]:
        try:
            old_pytest = os.environ.get("OCP_VSCODE_PYTEST")
            os.environ["OCP_VSCODE_PYTEST"] = "1"
            from ocp_vscode.show import _convert

            converted, mapping = _convert(obj, progress=None)
            return {
                "instances": converted[0],
                "shapes": converted[1],
                "config": converted[2],
                "count": converted[3],
                "mapping": mapping,
            }
        except Exception as exc:
            raise ForgeCADError(
                "TESSELLATION_FAILED",
                str(exc),
                details={"traceback": traceback.format_exc()},
                recoverable=True,
            ) from exc
        finally:
            if old_pytest is None:
                os.environ.pop("OCP_VSCODE_PYTEST", None)
            else:
                os.environ["OCP_VSCODE_PYTEST"] = old_pytest

    def export_stl(self, obj: Any, output_path: str) -> dict[str, Any]:
        cq = self._optional_import("cadquery")
        shape = self._shape_from_object(obj)
        if shape is None:
            raise ForgeCADError(
                "NO_BREP_HANDLE",
                "This revision does not have a BRep handle available for STL export",
                recoverable=True,
            )
        if cq is None:
            raise self._dependency_error("cadquery")

        try:
            cq.exporters.export(shape, output_path, "STL")
            size = os.path.getsize(output_path)
            return {"output_path": output_path, "format": "stl", "size_bytes": size}
        except Exception as exc:
            raise ForgeCADError(
                "STL_EXPORT_FAILED",
                str(exc),
                details={"traceback": traceback.format_exc()},
                recoverable=True,
            ) from exc

    def _assembly_tree(self, assembly: Any) -> dict[str, Any]:
        def walk(node: Any, path: str) -> dict[str, Any]:
            node_name = node.name or "root"
            current_path = f"{path}/{node_name}" if path else f"/{node_name}"
            return {
                "id": current_path,
                "name": node_name,
                "type": "Assembly",
                "children": [
                    walk(child, current_path)
                    for child in getattr(node, "children", [])
                ],
            }

        return walk(assembly, "")

    def _shape_from_object(self, obj: Any) -> Any:
        if obj is None:
            return None
        if hasattr(obj, "val") and callable(obj.val):
            try:
                return obj.val()
            except Exception:
                pass
        if hasattr(obj, "toCompound") and callable(obj.toCompound):
            try:
                return obj.toCompound()
            except Exception:
                pass
        if hasattr(obj, "wrapped"):
            return obj
        return None

    def _can_import(self, name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def _optional_import(self, name: str) -> Any:
        if not self._can_import(name):
            return None
        return importlib.import_module(name)

    def _dependency_error(self, package: str) -> ForgeCADError:
        return ForgeCADError(
            "DEPENDENCY_MISSING",
            f"CAD dependency {package!r} is not installed in this Python environment",
            details={"package": package, "dependency_status": self.dependency_status()},
            recoverable=True,
        )
