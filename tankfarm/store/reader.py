"""Read helpers for the data directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tankfarm.errors import StoreError


class JsonReader:
    """Reads JSON documents and JSONL files; missing files read as empty."""

    def read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StoreError(str(path), str(exc)) from exc

    def read_lines(self, path: Path) -> tuple[dict[str, Any], ...]:
        if not path.is_file():
            return ()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - depends on the file system
            raise StoreError(str(path), str(exc)) from exc
        items: list[dict[str, Any]] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                items.append(json.loads(stripped))
            except ValueError as exc:
                raise StoreError(str(path), str(exc)) from exc
        return tuple(items)
