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
