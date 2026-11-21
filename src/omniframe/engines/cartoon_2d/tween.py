"""Interpolation curves for the 2D cartoon pipeline."""

from __future__ import annotations

import math
from typing import Any

#: The curve kinds the pipeline understands.
EASING_KINDS = (
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "bezier",
    "step",
    "hold",
)


class Easing:
    """An interpolation curve.

    Instances are immutable in practice; use :meth:`from_value` to build one
    from a string, a mapping or another ``Easing``.
    """

    __slots__ = ("kind", "control", "steps")

    def __init__(
        self,
        kind: str = "linear",
        control: list[float] | None = None,
        steps: int = 1,
    ) -> None:
        kind = str(getattr(kind, "value", kind)).lower()
        if kind not in EASING_KINDS:
            raise ValueError(f"Unknown easing '{kind}'. Expected one of {EASING_KINDS}.")
        self.kind = kind
        self.control = list(control) if control else [0.0, 0.0, 1.0, 1.0]
        self.steps = max(1, int(steps))

    # -- construction ---------------------------------------------------
    @classmethod
    def from_value(cls, value: Any) -> Easing:
        """Build an easing from a string, a mapping or an ``Easing``.

        Objects that merely expose a ``kind`` attribute are accepted too, so a
        schema-level easing model can be used directly.
        """

        if isinstance(value, Easing):
            return value
        if value is None:
            return cls()
        if isinstance(value, str):
            return cls(value)
        if isinstance(value, dict):
            return cls(
                str(value.get("kind", "linear")),
                value.get("control"),
                int(value.get("steps", 1)),
            )
        kind = getattr(value, "kind", None)
        if isinstance(kind, str):
            return cls(
                kind,
                getattr(value, "control", None),
                int(getattr(value, "steps", 1) or 1),
            )
        raise TypeError(f"Cannot build an Easing from {type(value).__name__}.")

    # -- evaluation -----------------------------------------------------
    def apply(self, t: float) -> float:
        """Map a normalised time ``t`` (0..1) through this curve."""

        t = min(1.0, max(0.0, float(t)))
        kind = self.kind

        if kind == "linear":
            return t
        if kind == "step":
            return math.floor(t * self.steps) / self.steps
        if kind == "hold":
            return 0.0
        if kind == "ease_in":
            return t * t
        if kind == "ease_out":
            return 1 - (1 - t) ** 2
        if kind == "ease_in_out":
            return 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2
        if kind == "bezier":
            return _bezier(t, self.control)
        return t

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Easing):
            return NotImplemented
        return (
            self.kind == other.kind
            and self.control == other.control
            and self.steps == other.steps
        )

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Easing(kind={self.kind!r}, steps={self.steps})"


def _bezier(t: float, control: list[float]) -> float:
    """Cubic bezier easing solved with bisection."""

    if len(control) < 4:
        return t
    x1, y1, x2, y2 = (float(c) for c in control[:4])

    def curve(u: float) -> tuple[float, float]:
        x = 3 * u * (1 - u) ** 2 * x1 + 3 * u * u * (1 - u) * x2 + u ** 3
        y = 3 * u * (1 - u) ** 2 * y1 + 3 * u * u * (1 - u) * y2 + u ** 3
        return x, y

    lo, hi = 0.0, 1.0
    u = t
    for _ in range(24):
        x, y = curve(u)
        if abs(x - t) < 1e-6:
            return y
        if x < t:
            lo = u
        else:
            hi = u
        u = (lo + hi) / 2
    return curve(u)[1]


def tween_value(a: float, b: float, t: float, easing: Any = "linear") -> float:
    """Interpolate between two scalars."""

    curve = Easing.from_value(easing)
    return float(a) + (float(b) - float(a)) * curve.apply(t)


def interpolate(a: Any, b: Any, t: float, easing: Any = "linear") -> Any:
    """Interpolate between two values of the same shape.

    Numbers interpolate directly, sequences element-wise and mappings
    key-wise.  Anything else falls back to a hard switch at ``t >= 1``.
    """

    curve = Easing.from_value(easing)
    eased = curve.apply(t)

    if isinstance(a, bool) or isinstance(b, bool):
        return b if eased >= 1.0 else a
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) + (float(b) - float(a)) * eased
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        size = min(len(a), len(b))
        values = [interpolate(a[i], b[i], eased, curve) for i in range(size)]
        return type(a)(values) if isinstance(a, tuple) else values
    if isinstance(a, dict) and isinstance(b, dict):
        shared = [key for key in a if key in b]
        return {key: interpolate(a[key], b[key], eased, curve) for key in shared}
    return b if eased >= 1.0 else a
