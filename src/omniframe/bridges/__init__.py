"""Host application bridges.

Each bridge adapts OmniFrame's universal project to one professional tool.
They are deliberately independent: an agent can use the Premiere bridge on a
machine that has no Premiere installed, because the bridge *generates* the
script and reports honestly that the host is missing.

    >>> from omniframe.bridges import get_bridge
    >>> get_bridge("capcut").detect().installed
    False
"""

from __future__ import annotations

from typing import Any

from .after_effects import AfterEffectsBridge
from .base import BridgeCapability, BridgeReport, BridgeTier, GeneratedScript, ToolBridge
from .capcut import CapCutBridge
from .davinci_resolve import DaVinciResolveBridge
from .krita import KritaBridge
from .premiere_pro import PremiereProBridge

__all__ = [
    "AfterEffectsBridge",
    "BRIDGES",
    "BridgeCapability",
    "BridgeReport",
    "BridgeTier",
    "CapCutBridge",
    "DaVinciResolveBridge",
    "GeneratedScript",
    "KritaBridge",
    "PremiereProBridge",
    "ToolBridge",
    "bridge_report",
    "get_bridge",
    "list_bridges",
]

#: Every bridge OmniFrame ships with, keyed by its stable identifier.
BRIDGES: dict[str, type[ToolBridge]] = {
    PremiereProBridge.id: PremiereProBridge,
    AfterEffectsBridge.id: AfterEffectsBridge,
    DaVinciResolveBridge.id: DaVinciResolveBridge,
    CapCutBridge.id: CapCutBridge,
    KritaBridge.id: KritaBridge,
}


def get_bridge(bridge_id: str) -> ToolBridge:
    """Instantiate the bridge registered as ``bridge_id``."""

    try:
        factory = BRIDGES[bridge_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown bridge '{bridge_id}'. Available: {', '.join(sorted(BRIDGES))}"
        ) from exc
    return factory()


def list_bridges() -> list[dict[str, Any]]:
    """Describe every bridge, including whether its host is installed."""

    out: list[dict[str, Any]] = []
    for bridge_id in sorted(BRIDGES):
        bridge = get_bridge(bridge_id)
        report = bridge.detect()
        out.append(
            {
                "id": bridge.id,
                "host": bridge.host,
                "description": bridge.description,
                "installed": report.installed,
                "scripting_api": report.scripting_api,
                "version": report.version,
                "capabilities": [c.to_dict() for c in bridge.capabilities()],
            }
        )
    return out


def bridge_report() -> list[dict[str, Any]]:
    """Return the raw detection report of every bridge."""

    return [get_bridge(bridge_id).detect().to_dict() for bridge_id in sorted(BRIDGES)]
