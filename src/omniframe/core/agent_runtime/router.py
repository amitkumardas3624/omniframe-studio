"""Planner / scene router: decide which engine should handle a shot.

The router is intentionally explainable.  Every routing decision returns the
candidate list with the score and the reason, so an agent can audit *why* a
shot went to a particular engine and override it explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import detect_environment
from ..logging import get_logger

LOG = get_logger("core.agent_runtime.router")


@dataclass(frozen=True)
class EngineDescriptor:
    """Static description of a render engine."""

    id: str
    description: str
    capabilities: frozenset[str] = frozenset()
    #: Host capabilities that must be present for this engine to be usable.
    requires: tuple[str, ...] = ()
    #: Higher priority wins ties.
    priority: int = 0
    #: Fallback engines are only used when nothing else matches.
    fallback: bool = False


@dataclass
class RoutingRequest:
    """What the planner knows about a shot or task."""

    #: The capability the task needs, e.g. ``code_scene`` or ``nle_timeline``.
    capability: str | None = None
    #: Extra capabilities that must all be supported.
    required_capabilities: list[str] = field(default_factory=list)
    #: An engine the caller explicitly asked for.
    preferred_engine: str | None = None
    #: Engines the caller wants to avoid.
    excluded_engines: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineChoice:
    """The routing outcome."""

    engine: str | None
    available: bool
    score: float
    reason: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "available": self.available,
            "score": self.score,
            "reason": self.reason,
            "alternatives": self.alternatives,
            "candidates": self.candidates,
        }


DEFAULT_ENGINES: tuple[EngineDescriptor, ...] = (
    EngineDescriptor(
        id="code_html_js",
        description="Deterministic HTML/CSS/JS/Canvas/WebGL frame renderer.",
        capabilities=frozenset(
            {"code_scene", "motion_graphics", "kinetic_type", "data_animation", "transparent_overlay"}
        ),
        requires=("chromium",),
        priority=60,
    ),
    EngineDescriptor(
        id="cartoon_2d",
        description="Frame-by-frame 2D cartoon pipeline with layers and x-sheets.",
        capabilities=frozenset({"2d_cartoon", "character_animation", "lip_sync", "x_sheet"}),
        requires=(),
        priority=55,
    ),
    EngineDescriptor(
        id="ffmpeg_compositor",
        description="FFmpeg based assembly, mixing, subtitles and export.",
        capabilities=frozenset({"composite", "audio_mix", "subtitle", "encode", "export"}),
        requires=("ffmpeg",),
        priority=40,
    ),
    EngineDescriptor(
        id="after_effects",
        description="Adobe After Effects bridge (ExtendScript driven).",
        capabilities=frozenset({"motion_fx", "nle_timeline", "vfx_composite", "expression"}),
        requires=("after_effects",),
        priority=80,
    ),
    EngineDescriptor(
        id="premiere_pro",
        description="Adobe Premiere Pro bridge (ExtendScript / UXP driven).",
        capabilities=frozenset({"nle_timeline", "edit", "audio_edit", "deliver"}),
        requires=("premiere_pro",),
        priority=78,
    ),
    EngineDescriptor(
        id="davinci_resolve",
        description="DaVinci Resolve bridge (Python / Lua scripting driven).",
        capabilities=frozenset({"nle_timeline", "edit", "color_grade", "fusion"}),
        requires=("davinci_resolve",),
        priority=76,
    ),
    EngineDescriptor(
        id="capcut",
        description="CapCut bridge (draft project generation).",
        capabilities=frozenset({"nle_timeline", "edit", "social_video"}),
        requires=("capcut",),
        priority=50,
    ),
)


class EngineRouter:
    """Chooses an engine for a task, given what is installed on this machine."""

    def __init__(
        self,
        engines: tuple[EngineDescriptor, ...] | None = None,
        *,
        available_capabilities: set[str] | None = None,
    ) -> None:
        self.engines = list(engines or DEFAULT_ENGINES)
        self._available = available_capabilities

    # -- capabilities ---------------------------------------------------
    @property
    def available_capabilities(self) -> set[str]:
        if self._available is not None:
            return self._available
        report = detect_environment()
        caps = {c["name"] for c in report["capabilities"] if c["available"]}
        # A host being present implies its scripting bridge is usable.
        if "davinci_resolve" in caps:
            caps.add("resolve_scripting")
        return caps

    def refresh(self) -> set[str]:
        """Re-probe the host and return the refreshed capability set."""

        report = detect_environment()
        self._available = {c["name"] for c in report["capabilities"] if c["available"]}
        return self._available

    def engine(self, engine_id: str) -> EngineDescriptor | None:
        for descriptor in self.engines:
            if descriptor.id == engine_id:
                return descriptor
        return None

    # -- routing --------------------------------------------------------
    def route(self, request: RoutingRequest) -> EngineChoice:
        """Route ``request`` to the best available engine."""

        available = self.available_capabilities
        candidates: list[dict[str, Any]] = []

        for descriptor in self.engines:
            if descriptor.id in request.excluded_engines:
                continue

            missing = [req for req in descriptor.requires if req not in available]
            score = float(descriptor.priority)

            if request.capability and request.capability in descriptor.capabilities:
                score += 30
            if request.required_capabilities:
                if all(cap in descriptor.capabilities for cap in request.required_capabilities):
                    score += 20
                else:
                    score -= 25
            if request.preferred_engine == descriptor.id:
                score += 40
            if missing:
                score -= 70

            candidates.append(
                {
                    "engine": descriptor.id,
                    "score": round(score, 2),
                    "available": not missing,
                    "missing_requirements": missing,
                    "capabilities": sorted(descriptor.capabilities),
                    "description": descriptor.description,
                    "fallback": descriptor.fallback,
                }
            )

        # When a capability is requested, only engines that actually support it
        # are eligible.  Falling back to an unrelated engine would silently
        # produce the wrong kind of output.
        if request.capability:
            supporting = [
                descriptor.id
                for descriptor in self.engines
                if request.capability in descriptor.capabilities
            ]
            eligible = [c for c in candidates if c["engine"] in supporting]
            if eligible:
                candidates = eligible

        candidates.sort(key=lambda c: (c["available"], c["score"]), reverse=True)

        if not candidates:
            return EngineChoice(
                engine=None,
                available=False,
                score=0.0,
                reason=(
                    f"No engine supports the capability '{request.capability}'."
                    if request.capability
                    else "No engine matched the request."
                ),
            )

        best = candidates[0]
        if not best["available"]:
            missing = sorted({m for c in candidates for m in c["missing_requirements"]})
            reason = (
                f"Best match '{best['engine']}' is unavailable on this host; "
                f"missing: {', '.join(missing or best['missing_requirements'])}."
            )
            return EngineChoice(
                engine=None,
                available=False,
                score=best["score"],
                reason=reason,
                alternatives=[c["engine"] for c in candidates if c["available"]],
                candidates=candidates,
            )

        if request.preferred_engine and best["engine"] != request.preferred_engine:
            reason = (
                f"Preferred engine '{request.preferred_engine}' is unavailable or a worse "
                f"match; routed to '{best['engine']}'."
            )
        else:
            reason = f"Routed to '{best['engine']}' (score {best['score']})."

        return EngineChoice(
            engine=best["engine"],
            available=True,
            score=best["score"],
            reason=reason,
            alternatives=[c["engine"] for c in candidates[1:3] if c["available"]],
            candidates=candidates,
        )

    def describe(self) -> list[dict[str, Any]]:
        """Describe every engine with its current availability."""

        available = self.available_capabilities
        out = []
        for descriptor in self.engines:
            missing = [req for req in descriptor.requires if req not in available]
            out.append(
                {
                    "id": descriptor.id,
                    "description": descriptor.description,
                    "capabilities": sorted(descriptor.capabilities),
                    "requires": list(descriptor.requires),
                    "available": not missing,
                    "missing_requirements": missing,
                }
            )
        return out
