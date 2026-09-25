"""HTTP front end of the control service."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from tankfarm.console.handlers import Handlers
from tankfarm.console.routes import Router
from tankfarm.console.wiring import Services
from tankfarm.errors import ControlError


def split_addr(addr: str) -> tuple[str, int]:
    host, _, raw_port = addr.rpartition(":")
    if not raw_port:
        return "127.0.0.1", int(host or 8080)
    return host or "127.0.0.1", int(raw_port)


def build_handler(services: Services) -> type[BaseHTTPRequestHandler]:
    """Binds one service graph to a request handler class."""

    router = Router(Handlers(services))

    class ControlHandler(BaseHTTPRequestHandler):
        server_version = "tankfarm/0.4"
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802 - http.server naming
            self._handle("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle(self, method: str) -> None:
            parsed = urlparse(self.path)
            query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            payload, problem = self._read_body()
            if problem is not None:
                self._respond(400, problem)
                return
            try:
                status, body = router.dispatch(method, parsed.path, payload, query)
            except ControlError as exc:
                self._respond(409, exc.as_payload())
                return
            except ValueError as exc:
                self._respond(400, {"error": str(exc), "code": "bad_request"})
                return
            self._respond(status, body)

        def _read_body(self) -> tuple[dict[str, Any], dict[str, Any] | None]:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}, None
            raw = self.rfile.read(length)
            try:
                decoded = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return {}, {"error": "malformed json body", "code": "bad_request"}
            if not isinstance(decoded, dict):
                return {}, {"error": "body must be a json object", "code": "bad_request"}
            return decoded, None

        def _respond(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    ControlHandler.router = router  # type: ignore[attr-defined]
    return ControlHandler


class ControlServer:
    """Owns the listening socket."""

    def __init__(self, addr: str, services: Services) -> None:
        self.addr = addr
        self.services = services
        self.host, self.port = split_addr(addr)
        self._httpd: ThreadingHTTPServer | None = None

    def create(self) -> ThreadingHTTPServer:
        self._httpd = ThreadingHTTPServer((self.host, self.port), build_handler(self.services))
        return self._httpd

    def bound_port(self) -> int:
        if self._httpd is None:
            return self.port
        return int(self._httpd.server_address[1])

    def serve_forever(self) -> None:
        httpd = self.create()
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()

