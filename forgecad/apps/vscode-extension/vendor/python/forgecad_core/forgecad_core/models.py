"""Serializable ForgeCAD domain records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    root_path: str | None
    active_model_id: str | None = None
    active_revision_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "root_path": self.root_path,
            "active_model_id": self.active_model_id,
            "active_revision_id": self.active_revision_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class ModelRecord:
    model_id: str
    session_id: str
    name: str
    source_kind: str
    active_revision_id: str
    revision_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "session_id": self.session_id,
            "name": self.name,
            "source_kind": self.source_kind,
            "active_revision_id": self.active_revision_id,
            "revision_ids": list(self.revision_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class RevisionRecord:
    revision_id: str
    model_id: str
    session_id: str
    source_ref: dict[str, Any]
    metadata: dict[str, Any]
    scene_tree: dict[str, Any]
    tessellated_scene: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self, *, include_tessellation: bool = False) -> dict[str, Any]:
        data = {
            "revision_id": self.revision_id,
            "model_id": self.model_id,
            "session_id": self.session_id,
            "source_ref": self.source_ref,
            "metadata": self.metadata,
            "scene_tree": self.scene_tree,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "created_at": self.created_at,
            "has_tessellated_scene": self.tessellated_scene is not None,
        }
        if include_tessellation:
            data["tessellated_scene"] = self.tessellated_scene
        return data


@dataclass(slots=True)
class ServiceEvent:
    event_id: str
    event_type: str
    session_id: str | None = None
    model_id: str | None = None
    revision_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "session_id": self.session_id,
            "model_id": self.model_id,
            "revision_id": self.revision_id,
            "payload": self.payload,
            "created_at": self.created_at,
        }


def default_view_state() -> dict[str, Any]:
    return {
        "camera": None,
        "selected_shape_ids": [],
        "visible_node_states": {},
        "clipping": {},
        "active_analysis_tool": None,
        "viewport_size": None,
    }


@dataclass(slots=True)
class RendererRecord:
    renderer_id: str
    session_id: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    view_state: dict[str, Any] = field(default_factory=default_view_state)
    current_model_id: str | None = None
    current_revision_id: str | None = None
    latest_capture_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "renderer_id": self.renderer_id,
            "session_id": self.session_id,
            "capabilities": self.capabilities,
            "view_state": self.view_state,
            "current_model_id": self.current_model_id,
            "current_revision_id": self.current_revision_id,
            "latest_capture_id": self.latest_capture_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class RenderCommandRecord:
    command_id: str
    command: str
    session_id: str
    renderer_id: str | None = None
    model_id: str | None = None
    revision_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command": self.command,
            "session_id": self.session_id,
            "renderer_id": self.renderer_id,
            "model_id": self.model_id,
            "revision_id": self.revision_id,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class CaptureRecord:
    capture_id: str
    renderer_id: str
    session_id: str
    command_id: str | None
    image_base64: str
    mime_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    model_id: str | None = None
    revision_id: str | None = None
    view_state: dict[str, Any] = field(default_factory=default_view_state)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "renderer_id": self.renderer_id,
            "session_id": self.session_id,
            "command_id": self.command_id,
            "image_base64": self.image_base64,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "model_id": self.model_id,
            "revision_id": self.revision_id,
            "view_state": self.view_state,
            "created_at": self.created_at,
        }
