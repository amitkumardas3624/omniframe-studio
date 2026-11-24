"""Optional deterministic seek adapter for external animation libraries.

GSAP timelines, Lottie instances and Three.js scene state normally advance
themselves with a render loop.  This helper lets a scene register those
instances once (in ``bootstrap``) and scrub them from the scene's own
``seek(t)`` function.  The runtime holds registration metadata only: it never
reads a clock, starts a timer or keeps per-frame state, so rendering frame N
after frame N-1 produces exactly the same pixels as jumping straight to N.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ...core.errors import ValidationError

SEEK_KINDS = frozenset({"gsap", "lottie", "three", "custom"})


@dataclass(frozen=True)
class SeekBinding:
    """Description of one external animation instance to scrub."""

    name: str
    kind: str = "custom"
    start: float = 0.0
    duration: float | None = None
    track: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("A seek binding needs a non-empty name.")
        if self.kind not in SEEK_KINDS:
            raise ValidationError(
                "Unknown seek binding kind.", kind=self.kind, supported=sorted(SEEK_KINDS)
            )
        if not math.isfinite(self.start) or self.start < 0:
            raise ValidationError(
                "A seek binding start must be a finite, non-negative number.",
                name=self.name,
                start=self.start,
            )
        if self.duration is not None and (
            not math.isfinite(self.duration) or self.duration <= 0
        ):
            raise ValidationError(
                "A seek binding duration must be a finite positive number.",
                name=self.name,
                duration=self.duration,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "start": float(self.start),
            "duration": None if self.duration is None else float(self.duration),
            "track": self.track,
        }


def local_time(t: float, start: float, duration: float | None) -> float:
    """Pure local-time math shared with the JavaScript runtime contract.

    A binding is inactive before ``start`` and holds its final value after
    ``duration``.  The same clamping is implemented in :func:`seek_adapter_source`;
    the integration tests assert both agree.
    """

    local = float(t) - float(start)
    if local <= 0:
        return 0.0
    if duration is None:
        return local
    return min(local, float(duration))


def seek_adapter_source() -> str:
    """JavaScript installing the inert ``window.__omniframe_seek_adapter`` runtime.

    Register once from ``bootstrap``::

        window.__omniframe_seek_adapter.register('tl', timeline,
                                                 {kind: 'gsap', track: 'intro'});

    Then call ``seek(t, frame)`` from the scene's ``seek(t)``.  A missing
    library instance is skipped rather than throwing, so scenes that do not
    use GSAP/Lottie/Three.js stay unaffected.
    """

    kinds = ",".join(f"'{name}'" for name in sorted(SEEK_KINDS))
    return f"""(function () {{
    if (window.__omniframe_seek_adapter) return;
    var bindings = [];
    var supported = [{kinds}];

    function findTrack(id) {{
        var composition = window.__OMNIFRAME_COMPOSITION__;
        if (!id || !composition || !composition.tracks) return null;
        for (var i = 0; i < composition.tracks.length; i++) {{
            if (composition.tracks[i].id === id) return composition.tracks[i];
        }}
        return null;
    }}

    var runtime = {{
        register: function (name, target, options) {{
            if (!name || !target) return false;
            var opts = options || {{}};
            var kind = opts.kind || 'custom';
            if (supported.indexOf(kind) < 0) return false;

            var source = findTrack(opts.track);
            var start = source ? source.start : (Number(opts.start) || 0);
            var duration = source
                ? source.duration
                : ((opts.duration === undefined || opts.duration === null)
                   ? null : Number(opts.duration));
            var seek = (typeof opts.seek === 'function') ? opts.seek : null;

            var entry = {{ name: name, target: target, kind: kind,
                           start: start, duration: duration, seek: seek }};
            for (var i = 0; i < bindings.length; i++) {{
                if (bindings[i].name === name) {{ bindings[i] = entry; return true; }}
            }}
            bindings.push(entry);
            return true;
        }},

        seek: function (t, frame) {{
            var time = Number(t);
            var currentFrame = Number(frame) || 0;
            var fps = Number(window.__OMNIFRAME_FPS__) || 30;
            for (var i = 0; i < bindings.length; i++) {{
                var b = bindings[i];
                var local = time - b.start;
                if (local <= 0) local = 0;
                if (b.duration !== null && local > b.duration) local = b.duration;
                try {{
                    if (b.kind === 'gsap' && typeof b.target.time === 'function') {{
                        b.target.time(local, false);
                    }} else if (b.kind === 'lottie' &&
                               typeof b.target.goToAndStop === 'function') {{
                        b.target.goToAndStop(local * fps, true);
                    }} else if (b.kind === 'three' && typeof b.seek === 'function') {{
                        b.seek(local, time, currentFrame, b.target);
                    }} else if (b.kind === 'three' &&
                               typeof b.target.seek === 'function') {{
                        b.target.seek(local);
                    }} else if (b.kind === 'custom' && typeof b.seek === 'function') {{
                        b.seek(local, time, currentFrame, b.target);
                    }}
                }} catch (exc) {{
                    window.__OMNIFRAME_SEEK_ERRORS__ =
                        (window.__OMNIFRAME_SEEK_ERRORS__ || []).concat([String(exc)]);
                }}
            }}
        }},

        names: function () {{
            return bindings.map(function (b) {{ return b.name; }});
        }},

        reset: function () {{ bindings.length = 0; }}
    }};

    window.__omniframe_seek_adapter = runtime;
}})();"""
