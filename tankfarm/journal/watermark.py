"""Commit watermark position."""

from __future__ import annotations

from tankfarm.errors import WatermarkRegressionError


class Watermark:
    """Highest record sequence considered durable; never moves backwards."""

    def __init__(self, value: int = 0) -> None:
        self._value = int(value)

    def value(self) -> int:
        return self._value

    def advance_to(self, seq: int) -> int:
        candidate = int(seq)
        if candidate < self._value:
            raise WatermarkRegressionError(self._value, candidate)
        self._value = candidate
        return self._value

