from __future__ import annotations

import json
import base64
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
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

    def test_measure_revision_supports_dependency_free_measurements(self):
        service = ForgeCADService()
        session = service.create_session()
        result = service.accept_model(
            session_id=session["session_id"],
            name="accepted",
            metadata={"bounding_box": {"extents": [3, 4, 12]}},
        )

        measurements = service.measure_revision(
            result["model"]["model_id"],
            result["revision"]["revision_id"],
            [
                {"type": "bounding_box"},
                {"type": "point_distance", "point1": [0, 0, 0], "point2": [3, 4, 0]},
                {"type": "vector_angle", "vector1": [1, 0, 0], "vector2": [0, 1, 0]},
                {"type": "shape_properties"},
            ],
        )

        self.assertEqual(measurements["measurements"][0]["diagonal"], 13)
        self.assertEqual(measurements["measurements"][1]["distance"], 5)
        self.assertEqual(measurements["measurements"][2]["angle_degrees"], 90)
        self.assertEqual(
            measurements["measurements"][3]["error"]["code"],
            "NO_BREP_HANDLE",
        )

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
            measurements = _post(
                base + f"/models/{model_id}/revisions/{revision_id}/measure",
                {
                    "measurements": [
                        {
                            "type": "point_distance",
                            "point1": [0, 0, 0],
                            "point2": [0, 0, 2],
                        }
                    ]
                },
            )

            self.assertEqual(model_id, current["model"]["model_id"])
            self.assertEqual(current["revision"]["metadata"]["edge_count"], 12)
            self.assertEqual(metadata["metadata"]["edge_count"], 12)
            self.assertEqual(revision["revision_id"], revision_id)
            self.assertEqual(
                inspection["results"],
                [{"type": "edge_count", "value": 12}],
            )
            self.assertEqual(measurements["measurements"][0]["distance"], 2)
            self.assertTrue(_get(base + "/health")["ok"])
            options = _options(base + "/health", origin="vscode-webview://forgecad")
            self.assertEqual(options["status"], 204)
            self.assertEqual(
                options["headers"]["access-control-allow-origin"],
                "vscode-webview://forgecad",
            )
            blocked_options = _options(base + "/health", origin="https://example.com")
            self.assertNotIn(
                "access-control-allow-origin",
                blocked_options["headers"],
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_http_service_token_blocks_unauthorized_mutations(self):
        service = ForgeCADService()
        server = create_server(service, port=0, quiet=True, auth_token="secret-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            self.assertTrue(_get(base + "/health")["ok"])
            denied = _post_error(base + "/sessions", {"root_path": "/tmp/blocked"})
            self.assertEqual(denied["status"], 401)
            session = _post(
                base + "/sessions",
                {"root_path": "/tmp/auth"},
                headers={"x-forgecad-token": "secret-token"},
            )
            self.assertTrue(session["session_id"].startswith("session_"))
        finally:
            server.shutdown()
            server.server_close()

    def test_websocket_events_stream_live_events(self):
        service = ForgeCADService()
        server = create_server(service, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sock = _open_events_websocket(port)

        try:
            subscribed = _read_ws_json(sock)
            self.assertEqual(subscribed["event_type"], "events.subscribed")

            session = _post(base + "/sessions", {"root_path": "/tmp/ws"})
            event = _read_until_ws_event(sock, "session.created")

            self.assertEqual(event["session_id"], session["session_id"])
        finally:
            sock.close()
            service.store.events.emit("test.shutdown")
            server.shutdown()
            server.server_close()

    def test_websocket_events_do_not_replay_old_view_commands(self):
        service = ForgeCADService()
        session = service.create_session()
        service.set_camera(
            session_id=session["session_id"],
            camera={"position": [1, 2, 3]},
        )
        server = create_server(service, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        sock = _open_events_websocket(port)

        try:
            subscribed = _read_ws_json(sock)
            self.assertEqual(subscribed["event_type"], "events.subscribed")
            self.assertFalse(subscribed["payload"]["replay"])

            sock.settimeout(0.2)
            with self.assertRaises(socket.timeout):
                _read_ws_json(sock)

            sock.settimeout(5)
            service.set_camera(
                session_id=session["session_id"],
                camera={"position": [4, 5, 6]},
            )
            event = _read_until_ws_event(sock, "view.command")

            self.assertEqual(
                event["payload"]["command"]["payload"]["camera"]["position"],
                [4, 5, 6],
            )
        finally:
            sock.close()
            service.store.events.emit("test.shutdown")
            server.shutdown()
            server.server_close()


class Phase2RendererServiceTests(unittest.TestCase):
    def test_renderer_registers_and_reports_view_state(self):
        service = ForgeCADService()
        session = service.create_session()

        renderer = service.register_renderer(
            session_id=session["session_id"],
            capabilities={"commands": ["render_revision", "capture_view"]},
            view_state={
                "camera": {"position": [1, 2, 3]},
                "selected_shape_ids": ["solid:1"],
            },
        )["renderer"]

        self.assertEqual(renderer["session_id"], session["session_id"])
        self.assertEqual(renderer["view_state"]["camera"]["position"], [1, 2, 3])

        updated = service.update_renderer_view_state(
            renderer["renderer_id"],
            view_state={
                "camera": {"position": [3, 2, 1], "target": [0, 0, 0]},
                "visible_node_states": {"/result": [True, True]},
                "viewport_size": {"width": 800, "height": 600},
            },
            model_id="model_local",
            revision_id="rev_local",
        )

        view_state = service.get_renderer_view_state(renderer["renderer_id"])
        self.assertEqual(
            updated["renderer"]["view_state"]["visible_node_states"],
            {"/result": [True, True]},
        )
        self.assertEqual(view_state["model_id"], "model_local")
        self.assertEqual(view_state["view_state"]["viewport_size"]["width"], 800)

    def test_render_revision_resolves_active_model_and_emits_view_command(self):
        service = ForgeCADService()
        session = service.create_session()
        accepted = service.accept_model(
            session_id=session["session_id"],
            name="renderable",
            tessellated_scene={
                "instances": [],
                "shapes": {"bb": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1}},
                "config": {},
                "count": 1,
                "mapping": {},
            },
        )
        renderer = service.register_renderer(session_id=session["session_id"])[
            "renderer"
        ]

        result = service.render_revision(
            session_id=session["session_id"],
            renderer_id=renderer["renderer_id"],
        )
        command = result["command"]
        events = service.events()["events"]

        self.assertEqual(result["model_id"], accepted["model"]["model_id"])
        self.assertEqual(result["revision_id"], accepted["revision"]["revision_id"])
        self.assertEqual(command["command"], "render_revision")
        self.assertEqual(command["renderer_id"], renderer["renderer_id"])
        self.assertIn("tessellated_scene", command["payload"])
        self.assertEqual(events[-1]["event_type"], "view.command")
        self.assertEqual(events[-1]["payload"]["command"]["command_id"], command["command_id"])

    def test_capture_command_and_renderer_capture_roundtrip(self):
        service = ForgeCADService()
        session = service.create_session()
        accepted = service.accept_model(
            session_id=session["session_id"],
            name="capturable",
            tessellated_scene={"instances": [], "shapes": {}, "config": {}, "count": 0},
        )
        renderer = service.register_renderer(session_id=session["session_id"])[
            "renderer"
        ]

        request = service.capture_view(
            session_id=session["session_id"],
            renderer_id=renderer["renderer_id"],
        )
        capture = service.record_renderer_capture(
            renderer["renderer_id"],
            command_id=request["command"]["command_id"],
            image_base64="iVBORw0KGgo=",
            width=320,
            height=200,
            model_id=accepted["model"]["model_id"],
            revision_id=accepted["revision"]["revision_id"],
            view_state={"camera": {"zoom": 1.25}},
        )["capture"]
        stored_command = service.get_render_command(request["command"]["command_id"])[
            "command"
        ]
        view_state = service.get_view_state(renderer_id=renderer["renderer_id"])

        self.assertEqual(capture["mime_type"], "image/png")
        self.assertEqual(capture["width"], 320)
        self.assertEqual(stored_command["status"], "completed")
        self.assertEqual(view_state["renderer_id"], renderer["renderer_id"])
        self.assertEqual(view_state["model_id"], accepted["model"]["model_id"])
        self.assertEqual(view_state["view_state"]["camera"]["zoom"], 1.25)

    def test_capture_view_does_not_return_previous_capture_for_new_command(self):
        service = ForgeCADService()
        session = service.create_session()
        service.accept_model(
            session_id=session["session_id"],
            name="capturable",
            tessellated_scene={"instances": [], "shapes": {}, "config": {}, "count": 0},
        )
        renderer = service.register_renderer(session_id=session["session_id"])[
            "renderer"
        ]

        first_request = service.capture_view(
            session_id=session["session_id"],
            renderer_id=renderer["renderer_id"],
        )
        service.record_renderer_capture(
            renderer["renderer_id"],
            command_id=first_request["command"]["command_id"],
            image_base64="old-image",
        )
        second_request = service.capture_view(
            session_id=session["session_id"],
            renderer_id=renderer["renderer_id"],
        )

        self.assertNotEqual(
            first_request["command"]["command_id"],
            second_request["command"]["command_id"],
        )
        self.assertNotIn("capture", second_request)

    def test_http_renderer_command_endpoints(self):
        service = ForgeCADService()
        server = create_server(service, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            session = _post(base + "/sessions", {"root_path": "/tmp/phase2"})
            accepted = _post(
                base + "/models/accept",
                {
                    "session_id": session["session_id"],
                    "name": "http-renderable",
                    "tessellated_scene": {
                        "instances": [],
                        "shapes": {},
                        "config": {},
                        "count": 0,
                    },
                },
            )
            renderer = _post(
                base + "/renderers",
                {"session_id": session["session_id"], "capabilities": {"capture": True}},
            )["renderer"]
            render = _post(
                base + "/render/render_revision",
                {
                    "session_id": session["session_id"],
                    "renderer_id": renderer["renderer_id"],
                },
            )
            view_state = _post(
                base + "/render/get_view_state",
                {
                    "session_id": session["session_id"],
                    "renderer_id": renderer["renderer_id"],
                },
            )
            camera = _post(
                base + "/render/set_camera",
                {
                    "session_id": session["session_id"],
                    "renderer_id": renderer["renderer_id"],
                    "camera": {"position": [0, 0, 10]},
                },
            )

            self.assertEqual(render["model_id"], accepted["model"]["model_id"])
            self.assertEqual(render["command"]["command"], "render_revision")
            self.assertEqual(view_state["renderer_id"], renderer["renderer_id"])
            self.assertEqual(camera["command"]["command"], "set_camera")
        finally:
            server.shutdown()
            server.server_close()

    def test_http_renderer_commands_convert_array_like_tessellation_values(self):
        service = ForgeCADService()
        session = service.create_session()
        accepted = service.accept_model(
            session_id=session["session_id"],
            name="array-renderable",
            tessellated_scene={
                "instances": _ArrayLike([[1, 2, 3]]),
                "shapes": {"shape_1": {"vertices": _ArrayLike([[0.0, 1.0, 2.0]])}},
                "config": {},
                "count": _ScalarLike(1),
            },
        )
        renderer = service.register_renderer(session_id=session["session_id"])[
            "renderer"
        ]
        server = create_server(service, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            render = _post(
                base + "/render/render_revision",
                {
                    "session_id": session["session_id"],
                    "renderer_id": renderer["renderer_id"],
                },
            )
            scene = render["command"]["payload"]["tessellated_scene"]

            self.assertEqual(render["model_id"], accepted["model"]["model_id"])
            self.assertEqual(scene["instances"], [[1, 2, 3]])
            self.assertEqual(scene["shapes"]["shape_1"]["vertices"], [[0.0, 1.0, 2.0]])
            self.assertEqual(scene["count"], 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_http_renderer_commands_convert_opencascade_handles(self):
        service = ForgeCADService()
        session = service.create_session()
        service.accept_model(
            session_id=session["session_id"],
            name="ocp-renderable",
            tessellated_scene={
                "instances": [],
                "shapes": {},
                "config": {},
                "count": 1,
                "mapping": {
                    "parts": [
                        {
                            "shape": {
                                "name": "Workplane(Solid)",
                                "obj": _TopoDSLike(),
                            },
                            "loc": _TopLocLike(),
                        }
                    ]
                },
            },
        )
        renderer = service.register_renderer(session_id=session["session_id"])[
            "renderer"
        ]
        server = create_server(service, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            render = _post(
                base + "/render/render_revision",
                {
                    "session_id": session["session_id"],
                    "renderer_id": renderer["renderer_id"],
                },
            )
            part = render["command"]["payload"]["tessellated_scene"]["mapping"]["parts"][0]

            self.assertEqual(part["shape"]["obj"]["type"], "_TopoDSLike")
            self.assertEqual(part["shape"]["obj"]["shape_type"], "TopAbs_COMPOUND")
            self.assertEqual(part["loc"]["type"], "_TopLocLike")
            self.assertEqual(
                part["loc"]["transformation"]["matrix"],
                [[1.0, 0.0, 0.0, 4.0], [0.0, 1.0, 0.0, 5.0], [0.0, 0.0, 1.0, 6.0]],
            )
        finally:
            server.shutdown()
            server.server_close()


def _get(url: str):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(url: str, payload: dict, headers: dict | None = None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_error(url: str, payload: dict, headers: dict | None = None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return {
                "status": response.status,
                "body": json.loads(response.read().decode("utf-8")),
            }
    except HTTPError as error:
        try:
            return {
                "status": error.code,
                "body": json.loads(error.read().decode("utf-8")),
            }
        finally:
            error.close()


def _options(url: str, origin: str | None = None):
    headers = {"origin": origin} if origin else {}
    request = Request(url, headers=headers, method="OPTIONS")
    with urlopen(request, timeout=5) as response:
        return {
            "status": response.status,
            "headers": {key.lower(): value for key, value in response.headers.items()},
        }


def _open_events_websocket(port: int) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        "GET /events HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode("ascii"))
    response = _read_http_headers(sock)
    if b" 101 " not in response.split(b"\r\n", 1)[0]:
        raise AssertionError(response.decode("latin1"))
    return sock


def _read_http_headers(sock: socket.socket) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(1)
        if not chunk:
            raise AssertionError("Socket closed while reading HTTP headers")
        data += chunk
    return data


class _ArrayLike:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class _ScalarLike:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _TopoDSLike:
    __module__ = "OCP.OCP.TopoDS"

    def ShapeType(self):
        return "TopAbs_ShapeEnum.TopAbs_COMPOUND"

    def IsNull(self):
        return False

    def HashCode(self):
        return 123


class _TopLocLike:
    __module__ = "OCP.OCP.TopLoc"

    def IsIdentity(self):
        return False

    def Transformation(self):
        return _TrsfLike()


class _TrsfLike:
    def Value(self, row, column):
        values = {
            (1, 1): 1,
            (1, 4): 4,
            (2, 2): 1,
            (2, 4): 5,
            (3, 3): 1,
            (3, 4): 6,
        }
        return values.get((row, column), 0)

    def Form(self):
        return "gp_TrsfForm.gp_Identity"

    def ScaleFactor(self):
        return 1.0


def _read_until_ws_event(sock: socket.socket, event_type: str):
    for _ in range(10):
        event = _read_ws_json(sock)
        if event.get("event_type") == event_type:
            return event
    raise AssertionError(f"Did not receive WebSocket event {event_type!r}")


def _read_ws_json(sock: socket.socket):
    first = _recv_exact(sock, 1)[0]
    opcode = first & 0x0F
    if opcode != 1:
        raise AssertionError(f"Expected text frame, got opcode {opcode}")

    second = _recv_exact(sock, 1)[0]
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(_recv_exact(sock, 2), "big")
    elif length == 127:
        length = int.from_bytes(_recv_exact(sock, 8), "big")
    payload = _recv_exact(sock, length)
    return json.loads(payload.decode("utf-8"))


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise AssertionError("Socket closed while reading WebSocket frame")
        data += chunk
    return data


if __name__ == "__main__":
    unittest.main()
