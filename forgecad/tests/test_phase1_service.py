from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "forgecad" / "python" / "forgecad_core"))
sys.path.insert(0, str(ROOT / "forgecad" / "python" / "forgecad_service"))

from forgecad_core.errors import ForgeCADError
from forgecad_service import ForgeCADService
from forgecad_service.server import create_server


class Phase1ServiceTests(unittest.TestCase):
    def test_create_session_and_accept_model(self):
        service = ForgeCADService()
        session = service.create_session(root_path="/tmp/example")

        result = service.accept_model(
            session_id=session["session_id"],
            name="accepted-box",
            metadata={"bounding_box": {"extents": [1, 2, 3]}},
            scene_tree={"id": "/accepted-box", "name": "accepted-box", "children": []},
        )

        self.assertEqual(result["model"]["name"], "accepted-box")
        self.assertEqual(
            result["revision"]["metadata"]["bounding_box"]["extents"],
            [1, 2, 3],
        )

        current = service.current(session["session_id"])
        self.assertEqual(current["session"]["active_model_id"], result["model"]["model_id"])
        self.assertEqual(
            current["session"]["active_revision_id"],
            result["revision"]["revision_id"],
        )

    def test_inspect_accepted_model_uses_revision_metadata(self):
        service = ForgeCADService()
        session = service.create_session()
        result = service.accept_model(
            session_id=session["session_id"],
            name="accepted",
            metadata={"volume": 42, "face_count": 6},
        )

        inspection = service.inspect_revision(
            result["model"]["model_id"],
            result["revision"]["revision_id"],
            [{"type": "volume"}, {"type": "full"}, {"type": "list_faces"}],
        )

        self.assertEqual(inspection["results"][0], {"type": "volume", "value": 42})
        self.assertEqual(inspection["results"][1]["metadata"]["face_count"], 6)
        self.assertEqual(
            inspection["results"][2]["error"],
            "Unsupported Phase 1 query: list_faces",
        )

    def test_export_stl_without_brep_handle_returns_structured_error(self):
        service = ForgeCADService()
        session = service.create_session()
        result = service.accept_model(session_id=session["session_id"], name="accepted")

        with self.assertRaises(ForgeCADError) as raised:
            service.export_stl(
                result["model"]["model_id"],
                result["revision"]["revision_id"],
            )

        self.assertEqual(raised.exception.to_dict()["error"]["code"], "NO_BREP_HANDLE")

    def test_http_service_session_accept_and_current_roundtrip(self):
        service = ForgeCADService()
        server = create_server(service, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            session = _post(base + "/sessions", {"root_path": "/tmp/http"})
            accepted = _post(
                base + "/models/accept",
                {
                    "session_id": session["session_id"],
                    "name": "http-model",
                    "metadata": {"edge_count": 12},
                },
            )
            current = _get(base + f"/sessions/{session['session_id']}/current")
            model_id = accepted["model"]["model_id"]
            revision_id = accepted["revision"]["revision_id"]
            metadata = _get(
                base + f"/models/{model_id}/revisions/{revision_id}/metadata"
            )
            revision = _get(base + f"/models/{model_id}/revisions/{revision_id}")
            inspection = _post(
                base + f"/models/{model_id}/revisions/{revision_id}/inspect",
                {"queries": [{"type": "edge_count"}]},
            )

            self.assertEqual(model_id, current["model"]["model_id"])
            self.assertEqual(current["revision"]["metadata"]["edge_count"], 12)
            self.assertEqual(metadata["metadata"]["edge_count"], 12)
            self.assertEqual(revision["revision_id"], revision_id)
            self.assertEqual(
                inspection["results"],
                [{"type": "edge_count", "value": 12}],
            )
            self.assertTrue(_get(base + "/health")["ok"])
        finally:
            server.shutdown()
            server.server_close()


def _get(url: str):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(url: str, payload: dict):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
