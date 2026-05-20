"""In-memory ForgeCAD session/model/revision store."""

from __future__ import annotations

from itertools import count
from pathlib import Path
from typing import Any

from forgecad_core.errors import ForgeCADError
from forgecad_core.models import (
    CaptureRecord,
    ModelRecord,
    RenderCommandRecord,
    RendererRecord,
    RevisionRecord,
    SessionRecord,
    utc_now_iso,
)

from .events import EventLog


class InMemoryForgeCADStore:
    """A deterministic in-memory store for Phase 1.

    The service can later grow a persistent store without changing the domain
    vocabulary exposed to MCP and VS Code clients.
    """

    def __init__(self, events: EventLog | None = None) -> None:
        self.events = events or EventLog()
        self._session_counter = count(1)
        self._model_counter = count(1)
        self._revision_counter = count(1)
        self._renderer_counter = count(1)
        self._render_command_counter = count(1)
        self._capture_counter = count(1)
        self.sessions: dict[str, SessionRecord] = {}
        self.models: dict[str, ModelRecord] = {}
        self.revisions: dict[str, RevisionRecord] = {}
        self.handles: dict[str, Any] = {}
        self.renderers: dict[str, RendererRecord] = {}
        self.render_commands: dict[str, RenderCommandRecord] = {}
        self.captures: dict[str, CaptureRecord] = {}

    def create_session(self, root_path: str | None = None) -> SessionRecord:
        if root_path is not None:
            root_path = str(Path(root_path).expanduser())
        session = SessionRecord(
            session_id=f"session_{next(self._session_counter):06d}",
            root_path=root_path,
        )
        self.sessions[session.session_id] = session
        self.events.emit("session.created", session_id=session.session_id)
        return session

    def list_sessions(self) -> list[SessionRecord]:
        return list(self.sessions.values())

    def get_session(self, session_id: str) -> SessionRecord:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise ForgeCADError(
                "SESSION_NOT_FOUND",
                f"Session {session_id!r} was not found",
                details={"session_id": session_id},
            ) from exc

    def resolve_session(self, session_id: str | None) -> SessionRecord:
        if session_id:
            return self.get_session(session_id)
        if len(self.sessions) == 1:
            return next(iter(self.sessions.values()))
        raise ForgeCADError(
            "SESSION_REQUIRED",
            "A session_id is required when there is not exactly one session",
            details={"session_count": len(self.sessions)},
        )

    def create_model_revision(
        self,
        *,
        session_id: str,
        name: str,
        source_kind: str,
        source_ref: dict[str, Any],
        metadata: dict[str, Any],
        scene_tree: dict[str, Any],
        tessellated_scene: dict[str, Any] | None,
        handle: Any = None,
        warnings: list[str] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> tuple[ModelRecord, RevisionRecord]:
        session = self.get_session(session_id)
        model_id = f"model_{next(self._model_counter):06d}"
        revision_id = f"rev_{next(self._revision_counter):06d}"
        revision = RevisionRecord(
            revision_id=revision_id,
            model_id=model_id,
            session_id=session_id,
            source_ref=source_ref,
            metadata=metadata,
            scene_tree=scene_tree,
            tessellated_scene=tessellated_scene,
            warnings=warnings or [],
            errors=errors or [],
        )
        model = ModelRecord(
            model_id=model_id,
            session_id=session_id,
            name=name,
            source_kind=source_kind,
            active_revision_id=revision_id,
            revision_ids=[revision_id],
        )
        self.models[model_id] = model
        self.revisions[revision_id] = revision
        if handle is not None:
            self.handles[revision_id] = handle

        now = utc_now_iso()
        session.active_model_id = model_id
        session.active_revision_id = revision_id
        session.updated_at = now
        model.updated_at = now

        self.events.emit(
            "model.created",
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
        )
        self.events.emit(
            "revision.created",
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
        )
        return model, revision

    def get_model(self, model_id: str) -> ModelRecord:
        try:
            return self.models[model_id]
        except KeyError as exc:
            raise ForgeCADError(
                "MODEL_NOT_FOUND",
                f"Model {model_id!r} was not found",
                details={"model_id": model_id},
            ) from exc

    def get_revision(self, model_id: str, revision_id: str) -> RevisionRecord:
        model = self.get_model(model_id)
        if revision_id not in model.revision_ids:
            raise ForgeCADError(
                "REVISION_NOT_FOUND",
                f"Revision {revision_id!r} was not found for model {model_id!r}",
                details={"model_id": model_id, "revision_id": revision_id},
            )
        return self.revisions[revision_id]

    def get_handle(self, revision_id: str) -> Any:
        return self.handles.get(revision_id)

    def current(self, session_id: str | None = None) -> dict[str, Any]:
        session = self.resolve_session(session_id)
        data = {"session": session.to_dict(), "model": None, "revision": None}
        if session.active_model_id:
            model = self.get_model(session.active_model_id)
            data["model"] = model.to_dict()
        if session.active_revision_id and session.active_model_id:
            revision = self.get_revision(
                session.active_model_id,
                session.active_revision_id,
            )
            data["revision"] = revision.to_dict()
        return data

    def register_renderer(
        self,
        *,
        session_id: str,
        renderer_id: str | None = None,
        capabilities: dict[str, Any] | None = None,
        view_state: dict[str, Any] | None = None,
    ) -> RendererRecord:
        self.get_session(session_id)
        if renderer_id is None:
            renderer_id = f"renderer_{next(self._renderer_counter):06d}"

        now = utc_now_iso()
        renderer = self.renderers.get(renderer_id)
        if renderer is None:
            renderer = RendererRecord(
                renderer_id=renderer_id,
                session_id=session_id,
                capabilities=capabilities or {},
            )
            self.renderers[renderer_id] = renderer
            event_type = "renderer.attached"
        else:
            renderer.session_id = session_id
            renderer.capabilities = capabilities or renderer.capabilities
            renderer.updated_at = now
            event_type = "renderer.updated"

        if view_state is not None:
            renderer.view_state = self._normalized_view_state(view_state)
            renderer.updated_at = now

        self.events.emit(
            event_type,
            session_id=session_id,
            payload={"renderer": renderer.to_dict()},
        )
        return renderer

    def list_renderers(self, session_id: str | None = None) -> list[RendererRecord]:
        if session_id is None:
            return list(self.renderers.values())
        self.get_session(session_id)
        return [
            renderer
            for renderer in self.renderers.values()
            if renderer.session_id == session_id
        ]

    def get_renderer(self, renderer_id: str) -> RendererRecord:
        try:
            return self.renderers[renderer_id]
        except KeyError as exc:
            raise ForgeCADError(
                "RENDERER_NOT_FOUND",
                f"Renderer {renderer_id!r} was not found",
                details={"renderer_id": renderer_id},
            ) from exc

    def resolve_renderer(
        self,
        *,
        session_id: str | None = None,
        renderer_id: str | None = None,
    ) -> RendererRecord:
        if renderer_id:
            renderer = self.get_renderer(renderer_id)
            if session_id is not None and renderer.session_id != session_id:
                raise ForgeCADError(
                    "RENDERER_SESSION_MISMATCH",
                    f"Renderer {renderer_id!r} is not attached to session {session_id!r}",
                    details={
                        "renderer_id": renderer_id,
                        "session_id": session_id,
                        "renderer_session_id": renderer.session_id,
                    },
                )
            return renderer

        session = self.resolve_session(session_id)
        candidates = self.list_renderers(session.session_id)
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            return sorted(candidates, key=lambda item: item.updated_at)[-1]
        raise ForgeCADError(
            "RENDERER_NOT_FOUND",
            "No renderer is attached to this session",
            details={"session_id": session.session_id},
            recoverable=True,
        )

    def update_renderer_view_state(
        self,
        renderer_id: str,
        *,
        view_state: dict[str, Any],
        model_id: str | None = None,
        revision_id: str | None = None,
    ) -> RendererRecord:
        renderer = self.get_renderer(renderer_id)
        renderer.view_state = self._normalized_view_state(view_state)
        renderer.current_model_id = model_id
        renderer.current_revision_id = revision_id
        renderer.updated_at = utc_now_iso()
        self.events.emit(
            "view.state.updated",
            session_id=renderer.session_id,
            model_id=model_id,
            revision_id=revision_id,
            payload={"renderer": renderer.to_dict()},
        )
        return renderer

    def create_render_command(
        self,
        *,
        command: str,
        session_id: str,
        renderer_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RenderCommandRecord:
        self.get_session(session_id)
        command_id = f"render_cmd_{next(self._render_command_counter):08d}"
        record = RenderCommandRecord(
            command_id=command_id,
            command=command,
            session_id=session_id,
            renderer_id=renderer_id,
            model_id=model_id,
            revision_id=revision_id,
            payload=payload or {},
        )
        self.render_commands[command_id] = record
        self.events.emit(
            "view.command",
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
            payload={"command": record.to_dict()},
        )
        return record

    def get_render_command(self, command_id: str) -> RenderCommandRecord:
        try:
            return self.render_commands[command_id]
        except KeyError as exc:
            raise ForgeCADError(
                "RENDER_COMMAND_NOT_FOUND",
                f"Render command {command_id!r} was not found",
                details={"command_id": command_id},
            ) from exc

    def complete_render_command(self, command_id: str) -> RenderCommandRecord:
        command = self.get_render_command(command_id)
        command.status = "completed"
        command.updated_at = utc_now_iso()
        return command

    def record_capture(
        self,
        *,
        renderer_id: str,
        command_id: str | None,
        image_base64: str,
        mime_type: str = "image/png",
        width: int | None = None,
        height: int | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        view_state: dict[str, Any] | None = None,
    ) -> CaptureRecord:
        renderer = self.get_renderer(renderer_id)
        capture_id = f"capture_{next(self._capture_counter):08d}"
        capture = CaptureRecord(
            capture_id=capture_id,
            renderer_id=renderer_id,
            session_id=renderer.session_id,
            command_id=command_id,
            image_base64=image_base64,
            mime_type=mime_type,
            width=width,
            height=height,
            model_id=model_id,
            revision_id=revision_id,
            view_state=self._normalized_view_state(view_state or renderer.view_state),
        )
        self.captures[capture_id] = capture
        renderer.latest_capture_id = capture_id
        renderer.current_model_id = model_id or renderer.current_model_id
        renderer.current_revision_id = revision_id or renderer.current_revision_id
        renderer.view_state = capture.view_state
        renderer.updated_at = utc_now_iso()
        if command_id is not None:
            self.complete_render_command(command_id)
        self.events.emit(
            "render.capture.created",
            session_id=renderer.session_id,
            model_id=model_id,
            revision_id=revision_id,
            payload={
                "capture": capture.to_dict(),
                "renderer_id": renderer_id,
            },
        )
        return capture

    def get_capture(self, capture_id: str) -> CaptureRecord:
        try:
            return self.captures[capture_id]
        except KeyError as exc:
            raise ForgeCADError(
                "CAPTURE_NOT_FOUND",
                f"Capture {capture_id!r} was not found",
                details={"capture_id": capture_id},
            ) from exc

    def latest_capture_for_renderer(self, renderer_id: str) -> CaptureRecord | None:
        renderer = self.get_renderer(renderer_id)
        if renderer.latest_capture_id is None:
            return None
        return self.get_capture(renderer.latest_capture_id)

    def _normalized_view_state(self, view_state: dict[str, Any]) -> dict[str, Any]:
        return {
            "camera": view_state.get("camera"),
            "selected_shape_ids": list(view_state.get("selected_shape_ids") or []),
            "visible_node_states": dict(view_state.get("visible_node_states") or {}),
            "clipping": dict(view_state.get("clipping") or {}),
            "active_analysis_tool": view_state.get("active_analysis_tool"),
            "viewport_size": view_state.get("viewport_size"),
        }
