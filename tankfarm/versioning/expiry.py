"""Age based validity for versioned documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpiryPolicy:
    """``max_age`` counts logical ticks; ``0`` disables expiry."""

    max_age: int

    def age(self, issued_at: int, now: int) -> int:
        return int(now) - int(issued_at)

    def expired(self, issued_at: int, now: int) -> bool:
        if self.max_age <= 0:
            return False
        return self.age(issued_at, now) > self.max_age
