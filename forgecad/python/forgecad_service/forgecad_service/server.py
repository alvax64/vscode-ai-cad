"""Minimal HTTP API for the ForgeCAD service."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from forgecad_core.errors import ForgeCADError

from .service import ForgeCADService


class ForgeCADRequestHandler(BaseHTTPRequestHandler):
    service: ForgeCADService

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        self._handle("GET")

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        self._handle("POST")

    def _handle(self, method: str) -> None:
        try:
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
                        "details": {},
                        "recoverable": False,
                    }
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _dispatch(self, method: str) -> dict[str, Any]:
        path = urlparse(self.path).path.rstrip("/") or "/"
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
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def create_server(
    service: ForgeCADService,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    quiet: bool = False,
) -> ThreadingHTTPServer:
    class Handler(ForgeCADRequestHandler):
        pass

    Handler.service = service
    server = ThreadingHTTPServer((host, port), Handler)
    server.quiet = quiet  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the ForgeCAD shared service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    service = ForgeCADService()
    server = create_server(service, host=args.host, port=args.port, quiet=args.quiet)
    address = server.server_address
    print(f"ForgeCAD service listening on http://{address[0]}:{address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
