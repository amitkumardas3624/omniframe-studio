"""Deterministic composition metadata declared in an HTML scene template.

A template may declare variable defaults and per-element timing metadata with
plain ``data-*`` attributes.  This module reads them once, merges explicit
``scene.params`` over the declared defaults, and produces a small inert
JavaScript runtime.  Nothing here reads the clock, schedules a callback or
touches randomness: track time is always computed from a ``t`` supplied by the
scene's ``seek(t)`` function.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from ...core.errors import ValidationError

VARIABLES_ATTR = "data-composition-variables"
TRACK_ATTR = "data-track"
TRACK_INDEX_ATTR = "data-track-index"
START_ATTR = "data-start"
DURATION_ATTR = "data-duration"


@dataclass(frozen=True)
class TrackSpec:
    """Timing metadata for one element of a composition."""

    id: str
    start: float = 0.0
    duration: float | None = None
    track: int | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("A composition track needs a non-empty id.")
        if not math.isfinite(self.start) or self.start < 0:
            raise ValidationError(
                "A composition track start must be a finite, non-negative number.",
                id=self.id,
                start=self.start,
            )
        if self.duration is not None and (
            not math.isfinite(self.duration) or self.duration <= 0
        ):
            raise ValidationError(
                "A composition track duration must be a finite positive number.",
                id=self.id,
                duration=self.duration,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": float(self.start),
            "duration": None if self.duration is None else float(self.duration),
            "track": self.track,
        }


@dataclass(frozen=True)
class CompositionSpec:
    """What was declared by the template, before params are applied."""

    variables: dict[str, Any]
    tracks: tuple[TrackSpec, ...]

    def resolve(self, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Merge ``params`` over declared defaults without mutating the spec."""

        variables = dict(self.variables)
        if params:
            variables.update(dict(params))
        return {
            "variables": variables,
            "declared": list(self.variables),
            "tracks": [track.to_dict() for track in self.tracks],
        }


class _CompositionParser(HTMLParser):
    """Collect declarations in document order (later variables win)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.variables: dict[str, Any] = {}
        self.tracks: list[TrackSpec] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value for key, value in attrs if value is not None}
        if VARIABLES_ATTR in values:
            raw = values[VARIABLES_ATTR]
            try:
                declared = json.loads(raw)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "data-composition-variables must be a JSON object.",
                    value=raw[:120],
                ) from exc
            if not isinstance(declared, dict):
                raise ValidationError("data-composition-variables must be a JSON object.")
            self.variables.update(declared)

        if not any(
            key in values
            for key in (TRACK_ATTR, TRACK_INDEX_ATTR, START_ATTR, DURATION_ATTR)
        ):
            return

        index = len(self.tracks)
        track_id = values.get(TRACK_ATTR) or f"track-{index}"
        start = _number(values, START_ATTR, 0.0)
        duration = _number(values, DURATION_ATTR, None)
        raw_track_index = values.get(TRACK_INDEX_ATTR)
        track_index = _integer(raw_track_index) if raw_track_index is not None else None
        self.tracks.append(
            TrackSpec(
                id=track_id,
                start=start,
                duration=duration,
                track=track_index,
            )
        )


def _number(values: dict[str, str], key: str, default: float | None) -> float | None:
    if key not in values:
        return default
    try:
        return float(values[key])
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{key} must be a finite number.", attribute=key, value=values[key]
        ) from exc


def _integer(raw: str) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"{TRACK_INDEX_ATTR} must be an integer.", value=raw
        ) from exc


def parse_composition(html: str) -> CompositionSpec:
    """Read declarations from ``html``; raise ValidationError on bad metadata."""

    parser = _CompositionParser()
    parser.feed(html or "")
    parser.close()
    return CompositionSpec(
        variables=dict(parser.variables),
        tracks=tuple(parser.tracks),
    )


def resolve_composition(
    spec: CompositionSpec, params: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return the JSON-safe composition payload injected into a scene."""

    return spec.resolve(params)


def composition_source(resolved: Mapping[str, Any]) -> str:
    """JavaScript installing the composition globals and ``data-var`` bindings.

    The returned source is an IIFE with no timers, no animation frames, no wall
    clock and no randomness.  It is safe to evaluate once per page: every value
    comes from ``scene.params`` or the template declaration.
    """

    payload = json.dumps(dict(resolved), ensure_ascii=True).replace("<", "\\u003c")
    return f"""(function () {{
    var c = {payload};
    window.__OMNIFRAME_COMPOSITION__ = c;
    var tracks = c.tracks || [];

    window.__omniframe_track_local_time = function (id, t) {{
        var time = Number(t);
        for (var i = 0; i < tracks.length; i++) {{
            var track = tracks[i];
            if (track.id !== id) continue;
            var local = time - track.start;
            if (local <= 0) return 0;
            return track.duration === null ? local : Math.min(local, track.duration);
        }}
        return time;
    }};

    var vars = c.variables || {{}};
    var root = document.documentElement;
    Object.keys(vars).forEach(function (name) {{
        root.style.setProperty('--' + name, String(vars[name]));
    }});

    var nodes = document.querySelectorAll('[data-var]');
    for (var j = 0; j < nodes.length; j++) {{
        var name = nodes[j].getAttribute('data-var');
        if (Object.prototype.hasOwnProperty.call(vars, name)) {{
            nodes[j].textContent = String(vars[name]);
            nodes[j].setAttribute('data-omniframe-bound', name);
        }}
    }}
}})();"""
