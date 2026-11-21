"""Report feature loss during bridge translation/inspection.

``LossItem`` describes what happened to a single translated or inspected
feature, classified as one of ``supported``, ``degraded`` or ``unsupported``.
``LossReport`` groups several items for one bridge and can be serialised to a
JSON-friendly ``dict`` while also summarising how many items fall into each
status bucket.

The module is intentionally pure-stdlib and must never import from
``omniframe.bridges.base`` (or any bridge) so that ``base.py`` can import it
without creating an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["LossItem", "LossReport", "record_loss"]

#: Valid classifications for a loss item.
LOSS_STATUSES = ("supported", "degraded", "unsupported")


@dataclass
class LossItem:
    """A single feature and its translation/inspection outcome.

    ``status`` must be one of ``{"supported", "degraded", "unsupported"}``.
    """

    feature: str
    status: str
    reason: str = ""


@dataclass
class LossReport:
    """Grouped loss items for one bridge.

    ``total`` is the number of items the report is describing (usually
    ``len(items)`` but kept explicitly so callers may describe a larger
    expected set than the observed subset).
    """

    bridge: str
    total: int
    items: list[LossItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict (bridge + total + items + summary)."""
        return {
            "bridge": self.bridge,
            "total": self.total,
            "items": [
                {
                    "feature": item.feature,
                    "status": item.status,
                    "reason": item.reason,
                }
                for item in self.items
            ],
            "summary": self.summary(),
        }

    def summary(self) -> dict:
        """Count items by status, e.g. ``{"supported": 2, "degraded": 1, ...}``."""
        counts = {status: 0 for status in LOSS_STATUSES}
        for item in self.items:
            if item.status in counts:
                counts[item.status] += 1
        return counts


def record_loss(bridge: str, items: list[LossItem]) -> LossReport:
    """Build a :class:`LossReport` from a bridge id and loss items.

    ``report.total`` is set to ``len(items)``.
    """
    return LossReport(bridge=bridge, total=len(items), items=list(items))