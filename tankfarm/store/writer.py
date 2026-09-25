"""Append-only and atomic file writers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from tankfarm.errors import StoreError


class AtomicWriter:
    """Writes either a whole JSON document or one appended JSON line."""

    def write_json(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:  # pragma: no cover - depends on the file system
            raise StoreError(str(path), str(exc)) from exc

    def append_line(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
        except OSError as exc:  # pragma: no cover - depends on the file system
            raise StoreError(str(path), str(exc)) from exc

