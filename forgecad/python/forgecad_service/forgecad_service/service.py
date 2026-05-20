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
            "phase": 1,
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
