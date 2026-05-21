"""High-level ForgeCAD service operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forgecad_core.errors import ForgeCADError

from .runtime import GeometryRuntime
from .store import InMemoryForgeCADStore


class ForgeCADService:
    def __init__(
        self,
        *,
        store: InMemoryForgeCADStore | None = None,
        runtime: GeometryRuntime | None = None,
    ) -> None:
        self.store = store or InMemoryForgeCADStore()
        self.runtime = runtime or GeometryRuntime()

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "forgecad_service",
            "phase": 2,
            "dependencies": self.runtime.dependency_status(),
        }

    def create_session(self, root_path: str | None = None) -> dict[str, Any]:
        return self.store.create_session(root_path=root_path).to_dict()

    def list_sessions(self) -> dict[str, Any]:
        return {"sessions": [s.to_dict() for s in self.store.list_sessions()]}

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.store.get_session(session_id).to_dict()

    def current(self, session_id: str | None = None) -> dict[str, Any]:
        return self.store.current(session_id)

    def accept_model(
        self,
        *,
        session_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
        scene_tree: dict[str, Any] | None = None,
        tessellated_scene: dict[str, Any] | None = None,
        source_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model, revision = self.store.create_model_revision(
            session_id=session_id,
            name=name,
            source_kind="accepted",
            source_ref=source_ref or {"kind": "accepted"},
            metadata=metadata or {},
            scene_tree=scene_tree or {
                "id": "/result",
                "name": name,
                "type": "AcceptedModel",
                "children": [],
            },
            tessellated_scene=tessellated_scene,
        )
        return {
            "session_id": session_id,
            "model": model.to_dict(),
            "revision": revision.to_dict(include_tessellation=True),
        }

    def evaluate_script(
        self,
        *,
        session_id: str,
        script: str,
        name: str = "result",
        include_tessellation: bool = True,
        source_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.runtime.evaluate_script(
            script,
            name=name,
            include_tessellation=include_tessellation,
        )
        model, revision = self.store.create_model_revision(
            session_id=session_id,
            name=result.name,
            source_kind="script",
            source_ref=source_ref or {"kind": "inline_script"},
            metadata=result.metadata,
            scene_tree=result.scene_tree,
            tessellated_scene=result.tessellated_scene,
            handle=result.handle,
            warnings=result.warnings,
        )
        return {
            "session_id": session_id,
            "model": model.to_dict(),
            "revision": revision.to_dict(include_tessellation=True),
        }

    def get_revision(
        self,
        model_id: str,
        revision_id: str,
        *,
        include_tessellation: bool = False,
    ) -> dict[str, Any]:
        revision = self.store.get_revision(model_id, revision_id)
        return revision.to_dict(include_tessellation=include_tessellation)

    def get_tree(self, model_id: str, revision_id: str) -> dict[str, Any]:
        return self.store.get_revision(model_id, revision_id).scene_tree

    def get_metadata(self, model_id: str, revision_id: str) -> dict[str, Any]:
        revision = self.store.get_revision(model_id, revision_id)
        return {
            "session_id": revision.session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "metadata": revision.metadata,
        }

    def tessellate_revision(self, model_id: str, revision_id: str) -> dict[str, Any]:
        revision = self.store.get_revision(model_id, revision_id)
        if revision.tessellated_scene is None:
            handle = self.store.get_handle(revision_id)
            if handle is None:
                raise ForgeCADError(
                    "NO_BREP_HANDLE",
                    "This revision does not have a BRep handle available for tessellation",
                    details={"model_id": model_id, "revision_id": revision_id},
                    recoverable=True,
                )
            revision.tessellated_scene = self.runtime.tessellate(handle)
        return {
            "session_id": revision.session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "tessellated_scene": revision.tessellated_scene,
        }

    def inspect_revision(
        self,
        model_id: str,
        revision_id: str,
        queries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        revision = self.store.get_revision(model_id, revision_id)
        results: list[dict[str, Any]] = []
        metadata = revision.metadata
        for query in queries:
            qtype = query.get("type")
            if qtype == "full":
                results.append({"type": qtype, "metadata": metadata})
            elif qtype in metadata:
                results.append({"type": qtype, "value": metadata[qtype]})
            else:
                results.append(
                    {
                        "type": qtype,
                        "error": f"Unsupported Phase 1 query: {qtype}",
                    }
                )
        return {
            "session_id": revision.session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "results": results,
        }

    def measure_revision(
        self,
        model_id: str,
        revision_id: str,
        measurements: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        revision = self.store.get_revision(model_id, revision_id)
        handle = self.store.get_handle(revision_id)
        if measurements is None:
            measurements = [{"type": "bounding_box"}]
        result = self.runtime.measure(
            handle,
            measurements,
            metadata=revision.metadata,
        )
        return {
            "session_id": revision.session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "measurements": result["results"],
        }

    def export_stl(
        self,
        model_id: str,
        revision_id: str,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        revision = self.store.get_revision(model_id, revision_id)
        handle = self.store.get_handle(revision_id)
        if output_path is None:
            output_path = str(Path.cwd() / f"{model_id}_{revision_id}.stl")
        result = self.runtime.export_stl(handle, output_path)
        self.store.events.emit(
            "export.created",
            session_id=revision.session_id,
            model_id=model_id,
            revision_id=revision_id,
            payload=result,
        )
        return {
            "session_id": revision.session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "export": result,
        }

    def events(self) -> dict[str, Any]:
        return {"events": self.store.events.list_events()}

    def register_renderer(
        self,
        *,
        session_id: str,
        renderer_id: str | None = None,
        capabilities: dict[str, Any] | None = None,
        view_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        renderer = self.store.register_renderer(
            session_id=session_id,
            renderer_id=renderer_id,
            capabilities=capabilities,
            view_state=view_state,
        )
        return {"renderer": renderer.to_dict()}

    def list_renderers(self, session_id: str | None = None) -> dict[str, Any]:
        return {
            "renderers": [
                renderer.to_dict()
                for renderer in self.store.list_renderers(session_id=session_id)
            ]
        }

    def get_renderer(self, renderer_id: str) -> dict[str, Any]:
        return {"renderer": self.store.get_renderer(renderer_id).to_dict()}

    def update_renderer_view_state(
        self,
        renderer_id: str,
        *,
        view_state: dict[str, Any],
        model_id: str | None = None,
        revision_id: str | None = None,
    ) -> dict[str, Any]:
        renderer = self.store.update_renderer_view_state(
            renderer_id,
            view_state=view_state,
            model_id=model_id,
            revision_id=revision_id,
        )
        return {"renderer": renderer.to_dict()}

    def get_renderer_view_state(self, renderer_id: str) -> dict[str, Any]:
        renderer = self.store.get_renderer(renderer_id)
        return {
            "session_id": renderer.session_id,
            "renderer_id": renderer_id,
            "model_id": renderer.current_model_id,
            "revision_id": renderer.current_revision_id,
            "view_state": renderer.view_state,
        }

    def record_renderer_capture(
        self,
        renderer_id: str,
        *,
        command_id: str | None = None,
        image_base64: str,
        mime_type: str = "image/png",
        width: int | None = None,
        height: int | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        view_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        capture = self.store.record_capture(
            renderer_id=renderer_id,
            command_id=command_id,
            image_base64=image_base64,
            mime_type=mime_type,
            width=width,
            height=height,
            model_id=model_id,
            revision_id=revision_id,
            view_state=view_state,
        )
        return {"capture": capture.to_dict()}

    def get_render_command(self, command_id: str) -> dict[str, Any]:
        return {"command": self.store.get_render_command(command_id).to_dict()}

    def render_revision(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id, model_id, revision_id = self._resolve_revision_reference(
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
        )
        tessellation = self.tessellate_revision(model_id, revision_id)
        command = self._queue_render_command(
            "render_revision",
            session_id=session_id,
            renderer_id=renderer_id,
            model_id=model_id,
            revision_id=revision_id,
            payload={
                "config": config or {},
                "tessellated_scene": tessellation["tessellated_scene"],
            },
        )
        return {
            "session_id": session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "command": command,
            "tessellated_scene": tessellation["tessellated_scene"],
        }

    def capture_view(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id, model_id, revision_id = self._resolve_revision_reference(
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
        )
        command = self._queue_render_command(
            "capture_view",
            session_id=session_id,
            renderer_id=renderer_id,
            model_id=model_id,
            revision_id=revision_id,
            payload={"config": config or {}},
        )
        return {
            "session_id": session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "command": command,
        }

    def capture_overview(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        views: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id, model_id, revision_id = self._resolve_revision_reference(
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
        )
        command = self._queue_render_command(
            "capture_overview",
            session_id=session_id,
            renderer_id=renderer_id,
            model_id=model_id,
            revision_id=revision_id,
            payload={
                "views": views or ["front", "right", "top", "iso", "rear", "bottom"],
                "config": config or {},
            },
        )
        return {
            "session_id": session_id,
            "model_id": model_id,
            "revision_id": revision_id,
            "command": command,
        }

    def set_camera(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
        camera: dict[str, Any],
    ) -> dict[str, Any]:
        session = self.store.resolve_session(session_id)
        command = self._queue_render_command(
            "set_camera",
            session_id=session.session_id,
            renderer_id=renderer_id,
            payload={"camera": camera},
        )
        return {"session_id": session.session_id, "command": command}

    def set_visibility(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
        visible_node_states: dict[str, Any],
    ) -> dict[str, Any]:
        session = self.store.resolve_session(session_id)
        command = self._queue_render_command(
            "set_visibility",
            session_id=session.session_id,
            renderer_id=renderer_id,
            payload={"visible_node_states": visible_node_states},
        )
        return {"session_id": session.session_id, "command": command}

    def set_clipping(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
        clipping: dict[str, Any],
    ) -> dict[str, Any]:
        session = self.store.resolve_session(session_id)
        command = self._queue_render_command(
            "set_clipping",
            session_id=session.session_id,
            renderer_id=renderer_id,
            payload={"clipping": clipping},
        )
        return {"session_id": session.session_id, "command": command}

    def get_view_state(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
    ) -> dict[str, Any]:
        renderer = self.store.resolve_renderer(
            session_id=session_id,
            renderer_id=renderer_id,
        )
        return self.get_renderer_view_state(renderer.renderer_id)

    def _queue_render_command(
        self,
        command: str,
        *,
        session_id: str,
        renderer_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self.store.create_render_command(
            command=command,
            session_id=session_id,
            renderer_id=renderer_id,
            model_id=model_id,
            revision_id=revision_id,
            payload=payload,
        )
        return record.to_dict()

    def _resolve_revision_reference(
        self,
        *,
        session_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
    ) -> tuple[str, str, str]:
        if model_id is not None and revision_id is not None:
            revision = self.store.get_revision(model_id, revision_id)
            if session_id is not None and revision.session_id != session_id:
                raise ForgeCADError(
                    "REVISION_SESSION_MISMATCH",
                    "The requested revision does not belong to the requested session",
                    details={
                        "session_id": session_id,
                        "model_id": model_id,
                        "revision_id": revision_id,
                        "revision_session_id": revision.session_id,
                    },
                )
            return revision.session_id, model_id, revision_id

        current = self.current(session_id)
        session = current["session"]
        model = current["model"]
        revision = current["revision"]
        if model is None or revision is None:
            raise ForgeCADError(
                "NO_ACTIVE_MODEL",
                "No active model exists for this session",
                details={"session_id": session["session_id"]},
                recoverable=True,
            )
        if model_id is not None and model_id != model["model_id"]:
            raise ForgeCADError(
                "REVISION_REQUIRED",
                "A revision_id is required when model_id is not the active model",
                details={
                    "requested_model_id": model_id,
                    "active_model_id": model["model_id"],
                },
                recoverable=True,
            )
        if revision_id is not None and revision_id != revision["revision_id"]:
            raise ForgeCADError(
                "MODEL_REQUIRED",
                "A model_id is required when revision_id is not the active revision",
                details={
                    "requested_revision_id": revision_id,
                    "active_revision_id": revision["revision_id"],
                },
                recoverable=True,
            )
        return session["session_id"], model["model_id"], revision["revision_id"]
