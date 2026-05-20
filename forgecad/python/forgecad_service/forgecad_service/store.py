"""In-memory ForgeCAD session/model/revision store."""

from __future__ import annotations

from itertools import count
from pathlib import Path
from typing import Any

from forgecad_core.errors import ForgeCADError
from forgecad_core.models import (
    ModelRecord,
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
        self.sessions: dict[str, SessionRecord] = {}
        self.models: dict[str, ModelRecord] = {}
        self.revisions: dict[str, RevisionRecord] = {}
        self.handles: dict[str, Any] = {}

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
