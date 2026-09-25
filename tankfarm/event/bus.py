"""Synchronous topic bus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

Handler = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    topic: str
    value: Any
    ts: int


class EventBus:
    """Delivers each event to the handlers registered for its topic."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    def publish(self, event: Event) -> int:
        delivered = 0
        for handler in tuple(self._handlers.get(event.topic, ())):
            handler(event)
            delivered += 1
        return delivered

    def topics(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def close(self) -> None:
        self._handlers.clear()

