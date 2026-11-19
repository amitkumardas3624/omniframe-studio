"""Runtime configuration and host capability detection.

``omniframe doctor`` turns :func:`detect_environment` into a machine readable
report. Every detector is independent and never raises: an absent dependency
must degrade to "missing", never to a crash.
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .logging import get_logger

LOG = get_logger("core.config")

OMNIFRAME_HOME_ENV = "OMNIFRAME_HOME"
DEFAULT_HOME = ".omniframe"

#: Host applications we know how to bridge.  Keys are stable identifiers.
KNOWN_HOSTS = (
    "premiere_pro",
    "after_effects",
    "davinci_resolve",
    "capcut",
    "krita",
    "ffmpeg",
    "chromium",
)


@dataclass
class Capability:
    """A single detected capability on the current machine."""

    name: str
    available: bool
    version: str | None = None
    path: str | None = None
    detail: str | None = None
    source: str = "filesystem"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "version": self.version,
            "path": self.path,
            "detail": self.detail,
            "source": self.source,
        }


@dataclass
class Config:
    """Global, overridable OmniFrame settings."""

    home: Path
    log_level: str = "INFO"
    json_logs: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def checkpoints_dir(self) -> Path:
        return self.home / "checkpoints"

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    @property
    def renders_dir(self) -> Path:
        return self.home / "renders"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    def ensure_dirs(self) -> None:
        for path in (
            self.home,
            self.checkpoints_dir,
            self.cache_dir,
            self.renders_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home": str(self.home),
            "log_level": self.log_level,
            "json_logs": self.json_logs,
            "extras": self.extras,
        }


def get_config(home: str | os.PathLike[str] | None = None) -> Config:
    """Build a :class:`Config` from the environment."""

    raw_home = home or os.environ.get(OMNIFRAME_HOME_ENV) or (Path.cwd() / DEFAULT_HOME)
    return Config(
        home=Path(raw_home).expanduser().resolve(),
        log_level=os.environ.get("OMNIFRAME_LOG_LEVEL", "INFO"),
        json_logs=os.environ.get("OMNIFRAME_JSON_LOGS", "0") == "1",
    )


# --------------------------------------------------------------------------
# Individual detectors
# --------------------------------------------------------------------------

def _run_version(cmd: list[str], timeout: float = 8.0) -> str | None:
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - host dependent
        LOG.debug("version probe failed", extra={"cmd": cmd, "error": str(exc)})
        return None
    if proc.returncode != 0:
        return None
    out = (proc.stdout or proc.stderr or "").strip()
    return out.splitlines()[0] if out else None


def _first_existing(paths: list[str]) -> str | None:
    for candidate in paths:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def detect_python() -> Capability:
    return Capability(
        name="python",
        available=True,
        version=platform.python_version(),
        path=sys.executable,
        detail=f"running on {platform.system()} {platform.release()}",
        source="runtime",
    )


def detect_node() -> Capability:
    path = shutil.which("node")
    if not path:
        return Capability(name="node", available=False, detail="node executable not found on PATH")
    version = _run_version([path, "--version"])
    return Capability(name="node", available=True, version=version, path=path)


def detect_ffmpeg() -> Capability:
    path = shutil.which("ffmpeg")
    if not path:
        return Capability(name="ffmpeg", available=False, detail="ffmpeg not found on PATH")
    version = _run_version([path, "-version"])
    return Capability(name="ffmpeg", available=True, version=version, path=path)


def detect_ffprobe() -> Capability:
    path = shutil.which("ffprobe")
    if not path:
        return Capability(name="ffprobe", available=False, detail="ffprobe not found on PATH")
    version = _run_version([path, "-version"])
    return Capability(name="ffprobe", available=True, version=version, path=path)


def detect_playwright() -> Capability:
    """Check that the Playwright package and a Chromium build are present."""

    if importlib.util.find_spec("playwright") is None:
        return Capability(
            name="chromium",
            available=False,
            detail="playwright package not installed (pip install 'omniframe-studio[render]')",
            source="python-package",
        )
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - defensive
        return Capability(name="chromium", available=False, detail=f"playwright import failed: {exc}")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            version = browser.version
            browser.close()
    except Exception as exc:
        return Capability(
            name="chromium",
            available=False,
            detail=(
                "Chromium build missing - run `omniframe doctor --fix` "
                f"or `playwright install chromium` ({exc})"
            ),
            source="playwright",
        )
    return Capability(name="chromium", available=True, version=version, source="playwright")


def detect_adobe_premiere() -> Capability:
    candidates = [
        r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
        r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
        r"C:\Program Files\Adobe\Adobe Premiere Pro 2023\Adobe Premiere Pro.exe",
        "/Applications/Adobe Premiere Pro 2025/Adobe Premiere Pro.app",
        "/Applications/Adobe Premiere Pro 2024/Adobe Premiere Pro.app",
    ]
    path = _first_existing(candidates) or shutil.which("Adobe Premiere Pro.exe")
    if not path:
        return Capability(
            name="premiere_pro",
            available=False,
            detail="Premiere Pro executable not located",
        )
    return Capability(name="premiere_pro", available=True, path=path)


def detect_after_effects() -> Capability:
    candidates = [
        r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
        r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
        r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
        "/Applications/Adobe After Effects 2025/Adobe After Effects.app",
    ]
    path = _first_existing(candidates) or shutil.which("AfterFX.exe")
    if not path:
        return Capability(name="after_effects", available=False, detail="AfterFX.exe not located")
    return Capability(name="after_effects", available=True, path=path)


def detect_davinci_resolve() -> Capability:
    candidates = [
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
        "/Applications/DaVinci Resolve/DaVinci Resolve.app",
    ]
    path = _first_existing(candidates) or shutil.which("resolve")
    if not path:
        return Capability(name="davinci_resolve", available=False, detail="Resolve executable not located")
    detail = "Resolve present; scripting API requires the Studio edition"
    if "studio" not in path.lower():
        detail = "Resolve present but non-Studio build detected - external scripting is limited"
    return Capability(name="davinci_resolve", available=True, path=path, detail=detail)


def detect_capcut() -> Capability:
    candidates = [
        r"C:\Program Files\CapCut\CapCut.exe",
        r"C:\Users\%USERNAME%\AppData\Local\CapCut\Apps\CapCut.exe",
        "/Applications/CapCut.app",
    ]
    expanded = [os.path.expandvars(p) for p in candidates]
    path = _first_existing(expanded) or shutil.which("CapCut.exe")
    if not path:
        return Capability(name="capcut", available=False, detail="CapCut executable not located")
    return Capability(name="capcut", available=True, path=path)


def detect_krita() -> Capability:
    candidates = [
        r"C:\Program Files\Krita (64-bit)\bin\krita.exe",
        "/Applications/Krita.app/Contents/MacOS/krita",
    ]
    path = _first_existing(candidates) or shutil.which("krita")
    if not path:
        return Capability(name="krita", available=False, detail="krita executable not located")
    return Capability(name="krita", available=True, path=path)


DETECTORS = {
    "python": detect_python,
    "node": detect_node,
    "ffmpeg": detect_ffmpeg,
    "ffprobe": detect_ffprobe,
    "chromium": detect_playwright,
    "premiere_pro": detect_adobe_premiere,
    "after_effects": detect_after_effects,
    "davinci_resolve": detect_davinci_resolve,
    "capcut": detect_capcut,
    "krita": detect_krita,
}


def detect_environment(*, include_hosts: bool = True) -> dict[str, Any]:
    """Probe the machine and return a structured environment report."""

    names = list(DETECTORS)
    if not include_hosts:
        names = [n for n in names if n not in
                 {"premiere_pro", "after_effects", "davinci_resolve", "capcut", "krita"}]

    capabilities: list[Capability] = []
    for name in names:
        try:
            capabilities.append(DETECTORS[name]())
        except Exception as exc:  # pragma: no cover - detectors must never explode
            LOG.debug("detector raised", extra={"name": name, "error": str(exc)})
            capabilities.append(Capability(name=name, available=False, detail=f"detector error: {exc}"))

    cap_map = {c.name: c for c in capabilities}
    missing = [c.name for c in capabilities if not c.available]
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "capabilities": [c.to_dict() for c in capabilities],
        "capability_map": cap_map,
        "missing": missing,
        "ready": not any(
            c.name in {"ffmpeg", "chromium"} and not c.available for c in capabilities
        ),
    }


def write_report(report: dict[str, Any], path: str | os.PathLike[str]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return target
