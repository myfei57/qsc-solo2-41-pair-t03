"""On-disk layout of the data directory."""

from __future__ import annotations

from pathlib import Path


class StoreLayout:
    """Resolves the three files the service owns inside its data directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def ensure(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def journal_file(self) -> Path:
        return self._root / "journal.jsonl"

    def checkpoint_file(self) -> Path:
        return self._root / "checkpoint.json"

    def audit_file(self) -> Path:
        return self._root / "audit.jsonl"

