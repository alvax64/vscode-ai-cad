"""Minimal HTTP API for the ForgeCAD service."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty
from typing import Any
from urllib.parse import parse_qs, urlparse

from forgecad_core.errors import ForgeCADError
from forgecad_core.serialization import to_json_compatible

from .service import ForgeCADService


class ForgeCADRequestHandler(BaseHTTPRequestHandler):
    service: ForgeCADService

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        if self._is_events_websocket():
            self._handle_events_websocket()
            return
        self._handle("GET")

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        self._handle("POST")

    def do_OPTIONS(self) -> None:  # pylint: disable=invalid-name
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.send_header("content-length", "0")
        self.end_headers()

    def _handle(self, method: str) -> None:
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path.rstrip("/") or "/"
            query = parse_qs(parsed_url.query)
            if not self._is_authorized(method, path, query):
                self._send_json(
                    {
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "ForgeCAD service token is missing or invalid",
                            "details": {},
                            "recoverable": False,
                        }
                    },
                    status=HTTPStatus.UNAUTHORIZED,
                )
                return
            result = self._dispatch(method)
            self._send_json(result)
        except ForgeCADError as exc:
            status = HTTPStatus.BAD_REQUEST
            if exc.code.endswith("_NOT_FOUND"):
                status = HTTPStatus.NOT_FOUND
            self._send_json(exc.to_dict(), status=status)
        except Exception as exc:  # pylint: disable=broad-except
            self._send_json(
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": str(exc),
                        "details": {"traceback": traceback.format_exc()},
                        "recoverable": False,
                    }
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _dispatch(self, method: str) -> dict[str, Any]:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip("/") or "/"
        query = parse_qs(parsed_url.query)
        parts = [p for p in path.split("/") if p]
        body = self._read_body()

        if method == "GET" and path == "/health":
            return self.service.health()

        if method == "GET" and path == "/events":
            return self.service.events()

        if parts == ["sessions"] and method == "GET":
            return self.service.list_sessions()

        if parts == ["sessions"] and method == "POST":
            return self.service.create_session(root_path=body.get("root_path"))

        if len(parts) == 2 and parts[0] == "sessions" and method == "GET":
            return self.service.get_session(parts[1])

        if (
            len(parts) == 3
            and parts[0] == "sessions"
            and parts[2] == "current"
            and method == "GET"
        ):
            return self.service.current(parts[1])

        if parts == ["models", "accept"] and method == "POST":
            return self.service.accept_model(
                session_id=body["session_id"],
                name=body.get("name", "accepted-model"),
                metadata=body.get("metadata"),
                scene_tree=body.get("scene_tree"),
                tessellated_scene=body.get("tessellated_scene"),
                source_ref=body.get("source_ref"),
            )

        if parts == ["models", "evaluate"] and method == "POST":
            return self.service.evaluate_script(
                session_id=body["session_id"],
                script=body["script"],
                name=body.get("name", "result"),
                include_tessellation=body.get("include_tessellation", True),
                source_ref=body.get("source_ref"),
            )

        if parts == ["renderers"] and method == "GET":
            session_ids = query.get("session_id")
            return self.service.list_renderers(
                session_id=session_ids[0] if session_ids else None,
            )

        if parts == ["renderers"] and method == "POST":
            return self.service.register_renderer(
                session_id=body["session_id"],
                renderer_id=body.get("renderer_id"),
                capabilities=body.get("capabilities"),
                view_state=body.get("view_state"),
            )

        if len(parts) >= 2 and parts[0] == "renderers":
            renderer_id = parts[1]
            tail = parts[2:]
            if tail == [] and method == "GET":
                return self.service.get_renderer(renderer_id)
            if tail == ["view-state"] and method == "GET":
                return self.service.get_renderer_view_state(renderer_id)
            if tail == ["view-state"] and method == "POST":
                return self.service.update_renderer_view_state(
                    renderer_id,
                    view_state=body.get("view_state", {}),
                    model_id=body.get("model_id"),
                    revision_id=body.get("revision_id"),
                )
            if tail == ["captures"] and method == "POST":
                return self.service.record_renderer_capture(
                    renderer_id,
                    command_id=body.get("command_id"),
                    image_base64=body["image_base64"],
                    mime_type=body.get("mime_type", "image/png"),
                    width=body.get("width"),
                    height=body.get("height"),
                    model_id=body.get("model_id"),
                    revision_id=body.get("revision_id"),
                    view_state=body.get("view_state"),
                )

        if len(parts) == 3 and parts[:2] == ["render", "commands"] and method == "GET":
            return self.service.get_render_command(parts[2])

        if parts == ["render", "render_revision"] and method == "POST":
            return self.service.render_revision(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
                model_id=body.get("model_id"),
                revision_id=body.get("revision_id"),
                config=body.get("config"),
            )

        if parts == ["render", "capture"] and method == "POST":
            return self.service.capture_view(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
                model_id=body.get("model_id"),
                revision_id=body.get("revision_id"),
                config=body.get("config"),
            )

        if parts == ["render", "capture_overview"] and method == "POST":
            return self.service.capture_overview(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
                model_id=body.get("model_id"),
                revision_id=body.get("revision_id"),
                views=body.get("views"),
                config=body.get("config"),
            )

        if parts == ["render", "set_camera"] and method == "POST":
            return self.service.set_camera(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
                camera=body.get("camera", {}),
            )

        if parts == ["render", "set_visibility"] and method == "POST":
            return self.service.set_visibility(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
                visible_node_states=body.get("visible_node_states", {}),
            )

        if parts == ["render", "set_clipping"] and method == "POST":
            return self.service.set_clipping(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
                clipping=body.get("clipping", {}),
            )

        if parts == ["render", "get_view_state"] and method == "POST":
            return self.service.get_view_state(
                session_id=body.get("session_id"),
                renderer_id=body.get("renderer_id"),
            )

        if len(parts) >= 4 and parts[0] == "models" and parts[2] == "revisions":
            model_id = parts[1]
            revision_id = parts[3]
            tail = parts[4:]
            if tail == [] and method == "GET":
                return self.service.get_revision(model_id, revision_id)
            if tail == ["tree"] and method == "GET":
                return self.service.get_tree(model_id, revision_id)
            if tail == ["metadata"] and method == "GET":
                return self.service.get_metadata(model_id, revision_id)
            if tail == ["tessellate"] and method == "POST":
                return self.service.tessellate_revision(model_id, revision_id)
            if tail == ["inspect"] and method == "POST":
                return self.service.inspect_revision(
                    model_id,
                    revision_id,
                    body.get("queries", []),
                )
            if tail == ["measure"] and method == "POST":
                return self.service.measure_revision(
                    model_id,
                    revision_id,
                    body.get("measurements"),
                )
            if tail == ["export", "stl"] and method == "POST":
                return self.service.export_stl(
                    model_id,
                    revision_id,
                    body.get("output_path"),
                )

        raise ForgeCADError(
            "ROUTE_NOT_FOUND",
            f"No route for {method} {path}",
            details={"method": method, "path": path},
        )

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_json(
        self,
        data: Any,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        payload = json.dumps(
            to_json_compatible(data),
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self._send_cors_headers()
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("origin")
        if origin and self._is_allowed_origin(origin):
            self.send_header("access-control-allow-origin", origin)
            self.send_header("vary", "Origin")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type,x-forgecad-token")

    def _is_public_request(
        self,
        method: str,
        path: str,
    ) -> bool:
        return method == "GET" and path == "/health"

    def _is_authorized(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
    ) -> bool:
        token = getattr(self.server, "auth_token", None)
        if not token or self._is_public_request(method, path):
            return True
        provided = self.headers.get("x-forgecad-token")
        if provided is None:
            values = query.get("token")
            provided = values[0] if values else None
        if provided is None:
            return False
        return hmac.compare_digest(provided, token)

    def _is_allowed_origin(self, origin: str) -> bool:
        if origin.startswith("vscode-webview://"):
            return True
        if origin.startswith("https://") and origin.endswith(".vscode-cdn.net"):
            return True
        if self._is_loopback_origin(origin):
            return True
        allowed_origins = getattr(self.server, "cors_origins", set())
        return origin in allowed_origins

    def _is_loopback_origin(self, origin: str) -> bool:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"}:
            return False
        return parsed.hostname in {"127.0.0.1", "::1", "localhost"}

    def _is_events_websocket(self) -> bool:
        path = urlparse(self.path).path.rstrip("/") or "/"
        return (
            path == "/events"
            and self.headers.get("upgrade", "").lower() == "websocket"
        )

    def _handle_events_websocket(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip("/") or "/"
        query = parse_qs(parsed_url.query)
        if not self._is_authorized("GET", path, query):
            self._send_json(
                {
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "ForgeCAD service token is missing or invalid",
                        "details": {},
                        "recoverable": False,
                    }
                },
                status=HTTPStatus.UNAUTHORIZED,
            )
            return

        key = self.headers.get("sec-websocket-key")
        if not key:
            self._send_json(
                {
                    "error": {
                        "code": "WEBSOCKET_BAD_REQUEST",
                        "message": "Missing Sec-WebSocket-Key header",
                        "details": {},
                        "recoverable": True,
                    }
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        accept = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        subscription = self.service.store.events.subscribe(replay=False)
        self.close_connection = True
        try:
            self._send_websocket_message(
                {
                    "event_type": "events.subscribed",
                    "payload": {"replay": False},
                }
            )
            while True:
                try:
                    event = subscription.get(timeout=30)
                except Empty:
                    event = {"event_type": "events.heartbeat", "payload": {}}
                self._send_websocket_message(event)
        except (BrokenPipeError, ConnectionError, OSError):
            pass
        finally:
            subscription.close()

    def _send_websocket_message(self, message: dict[str, Any]) -> None:
        payload = json.dumps(
            to_json_compatible(message),
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        length = len(payload)
        header = bytearray([0x81])
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.extend((126, (length >> 8) & 0xFF, length & 0xFF))
        else:
            header.append(127)
            header.extend(length.to_bytes(8, "big"))
        self.wfile.write(bytes(header) + payload)
        self.wfile.flush()


def create_server(
    service: ForgeCADService,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    quiet: bool = False,
    auth_token: str | None = None,
    cors_origins: list[str] | None = None,
) -> ThreadingHTTPServer:
    class Handler(ForgeCADRequestHandler):
        pass

    Handler.service = service
    server = ThreadingHTTPServer((host, port), Handler)
    server.quiet = quiet  # type: ignore[attr-defined]
    server.auth_token = auth_token  # type: ignore[attr-defined]
    server.cors_origins = set(cors_origins or [])  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the ForgeCAD shared service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("FORGECAD_SERVICE_TOKEN"),
        help="Optional token required for non-health API requests",
    )
    parser.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        help="Additional allowed browser origin. VS Code WebView origins are always allowed.",
    )
    args = parser.parse_args(argv)

    service = ForgeCADService()
    server = create_server(
        service,
        host=args.host,
        port=args.port,
        quiet=args.quiet,
        auth_token=args.auth_token,
        cors_origins=args.cors_origin,
    )
    address = server.server_address
    print(f"ForgeCAD service listening on http://{address[0]}:{address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
