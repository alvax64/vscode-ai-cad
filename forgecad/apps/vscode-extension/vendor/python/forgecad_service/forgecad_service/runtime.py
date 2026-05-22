"""Geometry runtime for ForgeCAD Phase 1."""

from __future__ import annotations

import importlib
import importlib.util
import math
import os
import sys
import traceback
from dataclasses import dataclass
from typing import Any

from forgecad_core.display import (
    AnalysisTool,
    Camera,
    Collapse,
    DisplayContext,
    DisplayRequest,
    Render,
    StudioBackground,
    StudioEnvironment,
    StudioTextureMapping,
    StudioToneMapping,
    UiTab,
    display_context,
)
from forgecad_core.errors import ForgeCADError
from forgecad_core.serialization import to_json_compatible

TESSELLATION_DEFAULTS: dict[str, Any] = {
    "ambient_intensity": 1.0,
    "angular_tolerance": 0.2,
    "axes": False,
    "axes0": True,
    "black_edges": False,
    "center_grid": False,
    "collapse": 1,
    "control": "trackball",
    "default_color": "#e8b024",
    "default_edgecolor": "#707070",
    "default_facecolor": "Violet",
    "default_opacity": 0.5,
    "default_thickedgecolor": "MediumOrchid",
    "default_vertexcolor": "MediumOrchid",
    "deviation": 0.1,
    "direct_intensity": 1.1,
    "edge_accuracy": 0.001,
    "explode": False,
    "grid": False,
    "grid_font_size": 12,
    "helper_scale": 1.0,
    "metalness": 0.3,
    "ortho": True,
    "pan_speed": 1,
    "render_edges": True,
    "render_joints": False,
    "render_mates": False,
    "render_normals": False,
    "reset_camera": "reset",
    "rotate_speed": 1,
    "roughness": 0.65,
    "show_parent": False,
    "show_sketch_local": True,
    "ticks": 5,
    "timeit": False,
    "transparent": False,
    "tree_width": 240,
    "up": "Z",
    "zoom_speed": 1,
}


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
        namespace = self._script_namespace(cq)

        build123d = self._optional_import("build123d")
        if build123d is not None:
            namespace["bd"] = build123d
            namespace["build123d"] = build123d

        display = DisplayContext()
        try:
            old_no_show = os.environ.get("CADQUERY_NO_SHOW")
            os.environ["CADQUERY_NO_SHOW"] = "1"
            with display_context(display):
                exec(script, namespace)  # pylint: disable=exec-used
        except Exception as exc:
            raise ForgeCADError(
                "EVALUATION_FAILED",
                str(exc),
                details={"traceback": traceback.format_exc()},
                recoverable=True,
            ) from exc
        finally:
            if old_no_show is None:
                os.environ.pop("CADQUERY_NO_SHOW", None)
            else:
                os.environ["CADQUERY_NO_SHOW"] = old_no_show

        display_request = display.last_model_request()
        if display_request is not None:
            return self._display_request_result(
                display_request,
                fallback_name=name,
                include_tessellation=include_tessellation,
            )

        if "result" not in namespace:
            raise ForgeCADError(
                "RESULT_MISSING",
                "CAD script must define a variable named 'result' or call show(...)",
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

    def _script_namespace(self, cq: Any | None) -> dict[str, Any]:
        from forgecad_core import display as forgecad_display

        self._install_script_api_modules(forgecad_display)
        namespace: dict[str, Any] = {
            "__name__": "__forgecad_script__",
            "show": forgecad_display.show,
            "show_object": forgecad_display.show_object,
            "push_object": forgecad_display.push_object,
            "remove_object": forgecad_display.remove_object,
            "show_objects": forgecad_display.show_objects,
            "show_all": forgecad_display.show_all,
            "show_clear": forgecad_display.show_clear,
            "reset_show": forgecad_display.reset_show,
            "set_viewer_config": forgecad_display.set_viewer_config,
            "AnalysisTool": AnalysisTool,
            "Camera": Camera,
            "Collapse": Collapse,
            "Render": Render,
            "StudioBackground": StudioBackground,
            "StudioEnvironment": StudioEnvironment,
            "StudioTextureMapping": StudioTextureMapping,
            "StudioToneMapping": StudioToneMapping,
            "UiTab": UiTab,
        }
        if cq is not None:
            namespace["cq"] = cq
            namespace["cadquery"] = cq
        return namespace

    def _install_script_api_modules(self, forgecad_display: Any) -> None:
        exports = {
            name: getattr(forgecad_display, name)
            for name in getattr(forgecad_display, "__all__", [])
            if hasattr(forgecad_display, name)
        }
        forgecad_module = self._import_or_existing_module("forgecad")
        ocp_module = self._import_or_existing_module("ocp_vscode")
        for module_name in ("ocp_vscode.show", "ocp_vscode.config"):
            module = self._import_or_existing_module(module_name)
            for name, value in exports.items():
                setattr(module, name, value)
        for target in (forgecad_module, ocp_module):
            for name, value in exports.items():
                setattr(target, name, value)

    def _import_or_existing_module(self, module_name: str) -> Any:
        module = sys.modules.get(module_name)
        if module is not None and (module_name != "ocp_vscode" or hasattr(module, "__path__")):
            return module
        if module_name in sys.modules:
            del sys.modules[module_name]
        return importlib.import_module(module_name)

    def _display_request_result(
        self,
        request: DisplayRequest,
        *,
        fallback_name: str,
        include_tessellation: bool,
    ) -> EvaluationResult:
        model_name = request.model_name or fallback_name
        handle: Any
        if len(request.objects) == 1:
            handle = self._object_handle_from_display_payload(request.objects[0])
        else:
            handle = [self._object_handle_from_display_payload(obj) for obj in request.objects]

        metadata = self._metadata_from_display_request(request, handle)
        scene_tree = self._scene_tree_from_display_request(request, name=model_name)
        tessellated_scene = (
            self._tessellate_display_request(request)
            if include_tessellation
            else None
        )
        return EvaluationResult(
            name=model_name,
            handle=handle,
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
        accepted = self._accepted_tessellated_scene(obj)
        if accepted is not None:
            return accepted
        try:
            old_pytest = os.environ.get("OCP_VSCODE_PYTEST")
            os.environ["OCP_VSCODE_PYTEST"] = "1"
            return self._legacy_ocp_tessellate([obj], names=None, config={})
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

    def _tessellate_display_request(self, request: DisplayRequest) -> dict[str, Any]:
        accepted = self._accepted_tessellated_scene_from_request(request)
        if accepted is not None:
            return accepted
        try:
            old_pytest = os.environ.get("OCP_VSCODE_PYTEST")
            os.environ["OCP_VSCODE_PYTEST"] = "1"
            return self._legacy_ocp_tessellate(
                request.objects,
                names=request.names,
                colors=request.colors,
                alphas=request.alphas,
                modes=request.modes,
                materials=request.materials,
                config=request.config,
            )
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

    def _legacy_ocp_tessellate(
        self,
        objects: list[Any],
        *,
        names: list[str | None] | None,
        colors: list[Any | None] | None = None,
        alphas: list[float | None] | None = None,
        modes: list[str | None] | None = None,
        materials: list[Any | None] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            from ocp_tessellate.convert import (
                combined_bb,
                get_normal_len,
                tessellate_group,
                to_ocpgroup,
            )
            from ocp_tessellate.utils import Color
        except Exception as exc:
            raise self._dependency_error("ocp_tessellate") from exc

        config = self._tessellation_config(config)
        color_values = self._none_if_all_none(colors)
        color_objects = (
            None
            if color_values is None
            else [None if color is None else Color(color) for color in color_values]
        )
        alpha_values = self._none_if_all_none(alphas)
        material_values = self._none_if_all_none(materials)
        mode_values = self._none_if_all_none(modes)
        part_group, instances = to_ocpgroup(
            *objects,
            names=self._none_if_all_none(names),
            colors=color_objects,
            alphas=alpha_values,
            materials=material_values,
            modes=[self._render_mode_state(mode) for mode in mode_values] if mode_values else None,
            render_mates=config.get("render_mates", False),
            render_joints=config.get("render_joints", False),
            helper_scale=config.get("helper_scale", 1.0),
            default_color=config.get("default_color"),
            show_parent=config.get("show_parent", False),
            show_sketch_local=config.get("show_sketch_local", True),
            progress=None,
            debug=config.get("debug", False),
        )
        instances, shapes, mapping = tessellate_group(
            part_group,
            instances,
            config,
            None,
            config.get("timeit"),
        )
        shapes["bb"] = self._combined_bounding_box(combined_bb(shapes))
        config["render_edges"] = True
        config["normal_len"] = get_normal_len(
            bool(config.get("render_normals")),
            shapes,
            config.get("deviation", 0.1),
        )
        return to_json_compatible(
            {
                "instances": instances,
                "shapes": shapes,
                "config": config,
                "count": part_group.count_shapes(),
                "mapping": mapping,
            }
        )

    def _render_mode_state(self, mode: str | None) -> tuple[int, int] | None:
        return {
            "all": (1, 1),
            "edges": (0, 1),
            "faces": (1, 0),
            "none": (0, 0),
        }.get(mode or "")

    def _metadata_from_display_request(
        self,
        request: DisplayRequest,
        handle: Any,
    ) -> dict[str, Any]:
        accepted = self._accepted_metadata_from_request(request)
        if accepted is not None:
            return accepted
        if len(request.objects) == 1:
            return self.compute_metadata(handle)
        metadata = self.compute_metadata(handle)
        metadata["object_count"] = len(request.objects)
        metadata["display_names"] = list(request.names)
        return metadata

    def _scene_tree_from_display_request(
        self,
        request: DisplayRequest,
        *,
        name: str,
    ) -> dict[str, Any]:
        accepted = self._accepted_scene_tree_from_request(request)
        if accepted is not None:
            return accepted
        return {
            "id": "/result",
            "name": name,
            "type": "DisplayGroup" if len(request.objects) > 1 else type(request.objects[0]).__name__,
            "children": [
                {
                    "id": f"/result/{index}",
                    "name": item_name or f"Object {index + 1}",
                    "type": type(obj).__name__,
                    "children": [],
                    "render_mode": request.modes[index] if index < len(request.modes) else None,
                }
                for index, (item_name, obj) in enumerate(zip(request.names, request.objects))
            ],
        }

    def _object_handle_from_display_payload(self, obj: Any) -> Any:
        if isinstance(obj, dict) and "handle" in obj:
            return obj["handle"]
        return obj

    def _accepted_tessellated_scene_from_request(
        self,
        request: DisplayRequest,
    ) -> dict[str, Any] | None:
        if len(request.objects) != 1:
            return None
        return self._accepted_tessellated_scene(request.objects[0], config=request.config)

    def _accepted_tessellated_scene(
        self,
        obj: Any,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(obj, dict):
            return None
        if "tessellated_scene" in obj and isinstance(obj["tessellated_scene"], dict):
            scene = dict(obj["tessellated_scene"])
        elif "instances" in obj or "shapes" in obj:
            scene = dict(obj)
        else:
            return None
        if config:
            scene_config = dict(scene.get("config") or {})
            scene_config.update(config)
            scene["config"] = scene_config
        return to_json_compatible(scene)

    def _accepted_metadata_from_request(
        self,
        request: DisplayRequest,
    ) -> dict[str, Any] | None:
        if len(request.objects) != 1:
            return None
        obj = request.objects[0]
        if isinstance(obj, dict) and isinstance(obj.get("metadata"), dict):
            return to_json_compatible(obj["metadata"])
        scene = self._accepted_tessellated_scene(obj)
        if scene is None:
            return None
        return self._metadata_from_tessellated_scene(scene)

    def _accepted_scene_tree_from_request(
        self,
        request: DisplayRequest,
    ) -> dict[str, Any] | None:
        if len(request.objects) != 1:
            return None
        obj = request.objects[0]
        if isinstance(obj, dict) and isinstance(obj.get("scene_tree"), dict):
            return to_json_compatible(obj["scene_tree"])
        return None

    def _metadata_from_tessellated_scene(self, scene: dict[str, Any]) -> dict[str, Any]:
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
        bb = (scene.get("shapes") or {}).get("bb") if isinstance(scene.get("shapes"), dict) else None
        if isinstance(bb, dict):
            metadata["bounding_box"] = self._metadata_bbox_from_legacy_bb(bb)
        count = scene.get("count")
        if isinstance(count, int):
            metadata["shape_count"] = count
        return metadata

    def _metadata_bbox_from_legacy_bb(self, bb: dict[str, Any]) -> dict[str, Any] | None:
        try:
            xmin = float(bb["xmin"])
            ymin = float(bb["ymin"])
            zmin = float(bb["zmin"])
            xmax = float(bb["xmax"])
            ymax = float(bb["ymax"])
            zmax = float(bb["zmax"])
        except Exception:
            return None
        return {
            "min": [xmin, ymin, zmin],
            "max": [xmax, ymax, zmax],
            "extents": [xmax - xmin, ymax - ymin, zmax - zmin],
        }

    def _combined_bounding_box(self, bb: Any) -> dict[str, float]:
        if bb is None:
            return {
                "xmin": -1e-6,
                "ymin": -1e-6,
                "zmin": -1e-6,
                "xmax": 1e-6,
                "ymax": 1e-6,
                "zmax": 1e-6,
            }
        if hasattr(bb, "to_dict"):
            return bb.to_dict()
        return dict(bb)

    def _tessellation_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(TESSELLATION_DEFAULTS)
        for key, value in self._without_none_values(config or {}).items():
            if value is not None:
                merged[key] = value
        if isinstance(merged.get("grid"), bool):
            merged["grid"] = [merged["grid"]] * 3
        for key, default in TESSELLATION_DEFAULTS.items():
            if merged.get(key) is None:
                merged[key] = default
        return merged

    def _none_if_all_none(self, values: list[Any | None] | None) -> list[Any | None] | None:
        if values is None:
            return None
        return None if all(value is None for value in values) else values

    def _without_none_values(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._without_none_values(item)
                for key, item in value.items()
                if item is not None
            }
        if isinstance(value, list):
            return [self._without_none_values(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._without_none_values(item) for item in value)
        return value

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

    def measure(
        self,
        obj: Any,
        measurements: list[dict[str, Any]],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata or {}
        results = [
            self._measure_one(obj, measurement, metadata=metadata)
            for measurement in measurements
        ]
        return {"results": results}

    def _measure_one(
        self,
        obj: Any,
        measurement: dict[str, Any],
        *,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        mtype = measurement.get("type", "bounding_box")
        try:
            if mtype == "bounding_box":
                return self._measure_bounding_box(metadata)
            if mtype in ("point_distance", "distance_between_points"):
                return self._measure_point_distance(measurement)
            if mtype in ("vector_angle", "angle_between_vectors"):
                return self._measure_vector_angle(measurement)
            if mtype in ("shape_properties", "properties"):
                return self._measure_shape_properties(obj)
            if mtype in ("shape_distance", "distance"):
                return self._measure_shape_distance(obj, measurement)
        except ForgeCADError as exc:
            return {
                "type": mtype,
                "error": exc.to_dict()["error"],
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "type": mtype,
                "error": {
                    "code": "MEASUREMENT_FAILED",
                    "message": str(exc),
                    "details": {"traceback": traceback.format_exc()},
                    "recoverable": True,
                },
            }
        return {
            "type": mtype,
            "error": {
                "code": "MEASUREMENT_UNSUPPORTED",
                "message": f"Unsupported Phase 1 measurement type: {mtype}",
                "details": {"measurement": measurement},
                "recoverable": True,
            },
        }

    def _measure_bounding_box(self, metadata: dict[str, Any]) -> dict[str, Any]:
        bounding_box = metadata.get("bounding_box")
        if not bounding_box:
            raise ForgeCADError(
                "MEASUREMENT_DATA_MISSING",
                "Revision metadata does not include a bounding_box",
                recoverable=True,
            )
        extents = bounding_box.get("extents")
        diagonal = None
        if extents is not None and len(extents) == 3:
            diagonal = math.sqrt(sum(float(value) ** 2 for value in extents))
        return {
            "type": "bounding_box",
            "bounding_box": bounding_box,
            "diagonal": diagonal,
        }

    def _measure_point_distance(self, measurement: dict[str, Any]) -> dict[str, Any]:
        point1 = self._point(measurement.get("point1") or measurement.get("from"))
        point2 = self._point(measurement.get("point2") or measurement.get("to"))
        delta = [point2[index] - point1[index] for index in range(3)]
        return {
            "type": "point_distance",
            "distance": math.sqrt(sum(value * value for value in delta)),
            "delta": [abs(value) for value in delta],
            "point1": point1,
            "point2": point2,
        }

    def _measure_vector_angle(self, measurement: dict[str, Any]) -> dict[str, Any]:
        vector1 = self._point(measurement.get("vector1") or measurement.get("from"))
        vector2 = self._point(measurement.get("vector2") or measurement.get("to"))
        mag1 = math.sqrt(sum(value * value for value in vector1))
        mag2 = math.sqrt(sum(value * value for value in vector2))
        if mag1 == 0 or mag2 == 0:
            raise ForgeCADError(
                "MEASUREMENT_INVALID_INPUT",
                "Vectors must be non-zero",
                recoverable=True,
            )
        dot = sum(vector1[index] * vector2[index] for index in range(3))
        cosine = max(-1.0, min(1.0, dot / (mag1 * mag2)))
        return {
            "type": "vector_angle",
            "angle_degrees": math.degrees(math.acos(cosine)),
            "vector1": vector1,
            "vector2": vector2,
        }

    def _measure_shape_properties(self, obj: Any) -> dict[str, Any]:
        shape = self._shape_from_object(obj)
        if shape is None:
            raise ForgeCADError(
                "NO_BREP_HANDLE",
                "This revision does not have a BRep handle available for shape properties",
                recoverable=True,
            )
        try:
            from ocp_vscode.measure import get_properties

            return {"type": "shape_properties", "properties": get_properties(shape)}
        except Exception as exc:
            raise ForgeCADError(
                "MEASUREMENT_FAILED",
                str(exc),
                details={"traceback": traceback.format_exc()},
                recoverable=True,
            ) from exc

    def _measure_shape_distance(
        self,
        obj: Any,
        measurement: dict[str, Any],
    ) -> dict[str, Any]:
        shape = self._shape_from_object(obj)
        if shape is None:
            raise ForgeCADError(
                "NO_BREP_HANDLE",
                "This revision does not have a BRep handle available for shape distance",
                recoverable=True,
            )
        targets = measurement.get("targets") or []
        if targets not in ([], [{"kind": "root"}, {"kind": "root"}]):
            raise ForgeCADError(
                "MEASUREMENT_SELECTOR_UNSUPPORTED",
                "Phase 1 shape distance supports only the root revision shape",
                details={"targets": targets},
                recoverable=True,
            )
        try:
            from ocp_vscode.measure import get_distance

            return {
                "type": "shape_distance",
                "distance": get_distance(
                    shape,
                    shape,
                    center=bool(measurement.get("center", False)),
                ),
            }
        except Exception as exc:
            raise ForgeCADError(
                "MEASUREMENT_FAILED",
                str(exc),
                details={"traceback": traceback.format_exc()},
                recoverable=True,
            ) from exc

    def _point(self, value: Any) -> list[float]:
        if not isinstance(value, list | tuple) or len(value) != 3:
            raise ForgeCADError(
                "MEASUREMENT_INVALID_INPUT",
                "Expected a 3D point/vector array",
                details={"value": value},
                recoverable=True,
            )
        return [float(value[0]), float(value[1]), float(value[2])]

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
