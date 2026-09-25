"""Shared fixtures for the control service tests."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import pytest

from tankfarm.config.schema import DEFAULT_SETTINGS, ControlSettings
from tankfarm.console.server import ControlServer
from tankfarm.console.wiring import Services, build_services
from tankfarm.store.repository import Repository


class ApiClient:
    """HTTP client that returns the status code instead of raising."""

    def __init__(self, port: int) -> None:
        self.port = port

    def get(self, path: str, **query: object) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        cleaned = {key: value for key, value in query.items() if value is not None}
        if cleaned:
            url = f"{url}?{urlencode(cleaned)}"
        return self._send(url, None)

    def post(self, path: str, payload: dict | None = None) -> tuple[int, dict]:
        return self._send(f"http://127.0.0.1:{self.port}{path}", payload or {})

    def raw(self, path: str, body: bytes) -> tuple[int, dict]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=body
        )
        request.add_header("Content-Type", "application/json")
        return self._read(request)

    def _send(self, url: str, payload: dict | None) -> tuple[int, dict]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        return self._read(request)

    def _read(self, request: urllib.request.Request) -> tuple[int, dict]:
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "var"


@pytest.fixture
def settings(data_dir: Path) -> ControlSettings:
    return DEFAULT_SETTINGS.with_data_dir(str(data_dir))


@pytest.fixture
def services(settings: ControlSettings) -> Services:
    return build_services(settings, Repository(settings.data_dir))


@pytest.fixture
def restart(settings: ControlSettings):
    def _restart() -> Services:
        fresh = build_services(settings, Repository(settings.data_dir))
        fresh.restore()
        return fresh

    return _restart


@pytest.fixture
def handover(services: Services):
    def _run() -> str:
        services.persist_valves()
        services.change_tank()
        return services.persist_valves().sheet_id

    return _run


@pytest.fixture
def client(services: Services):
    server = ControlServer("127.0.0.1:0", services)
    httpd = server.create()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield ApiClient(server.bound_port())
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        services.bus.close()

