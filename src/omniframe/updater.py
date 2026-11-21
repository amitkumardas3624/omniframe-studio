"""Safe, optional GitHub update checks and explicit self-updates.

Normal OmniFrame commands only read the local update cache through
:func:`get_cached_update_advisory`; network access is reserved for explicit
checks and the update-status API.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__
from .core.config import get_config
from .core.logging import get_logger

LOG = get_logger("updater")

DEFAULT_REPO_SLUG = "amitkumardas3624/omniframe-studio"
DEFAULT_TTL_SECONDS = 6 * 60 * 60
DEFAULT_TIMEOUT_SECONDS = 4.0
_VERSION_RE = re.compile(r"(?P<core>\d+(?:\.\d+){0,3})(?P<suffix>[-+][0-9A-Za-z.-]+)?")

FetchJSON = Callable[[str], Any]
PopenFactory = Callable[..., Any]


def repo_slug() -> str:
    """Return the configured GitHub ``owner/repository`` slug."""

    return os.environ.get("OMNIFRAME_REPO_SLUG", DEFAULT_REPO_SLUG).strip() or DEFAULT_REPO_SLUG


def _cache_path(path: str | os.PathLike[str] | None = None) -> Path:
    configured = path or os.environ.get("OMNIFRAME_UPDATE_CACHE")
    if configured:
        return Path(configured).expanduser()
    return get_config().cache_dir / "update-status.json"


def _ttl_seconds() -> float:
    raw = os.environ.get("OMNIFRAME_UPDATE_TTL_SECONDS")
    try:
        return max(0.0, float(raw)) if raw is not None else DEFAULT_TTL_SECONDS
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _timeout_seconds() -> float:
    raw = os.environ.get("OMNIFRAME_UPDATE_TIMEOUT_SECONDS")
    try:
        return max(0.5, min(30.0, float(raw))) if raw is not None else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _parse_version(value: Any) -> tuple[tuple[int, int, int, int], tuple[str, ...] | None] | None:
    if value is None:
        return None
    match = _VERSION_RE.search(str(value).strip().lstrip("vV"))
    if not match:
        return None
    core = tuple(int(part) for part in match.group("core").split("."))
    padded = (core + (0, 0, 0, 0))[:4]
    suffix = match.group("suffix")
    if not suffix or suffix.startswith("+"):
        prerelease = None
    else:
        prerelease = tuple(part for part in suffix[1:].split(".") if part)
    return padded, prerelease


def normalize_version(value: Any) -> str | None:
    """Normalize a release/tag value to a comparable version string."""

    parsed = _parse_version(value)
    if parsed is None:
        return None
    core, prerelease = parsed
    normalized = ".".join(str(part) for part in core[:3])
    if prerelease:
        normalized += "-" + ".".join(prerelease)
    return normalized


def _compare_prerelease(left: tuple[str, ...] | None, right: tuple[str, ...] | None) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return 1
    if right is None:
        return -1
    for left_part, right_part in zip(left, right):
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_part) > int(right_part) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_part > right_part else -1
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def compare_versions(left: Any, right: Any) -> int:
    """Compare two semver-like values, returning ``-1``, ``0``, or ``1``."""

    parsed_left = _parse_version(left)
    parsed_right = _parse_version(right)
    if parsed_left is None or parsed_right is None:
        return 0
    if parsed_left[0] != parsed_right[0]:
        return 1 if parsed_left[0] > parsed_right[0] else -1
    return _compare_prerelease(parsed_left[1], parsed_right[1])


def _fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "omniframe-studio-updater",
        },
    )
    with urlopen(request, timeout=_timeout_seconds()) as response:  # noqa: S310 - fixed HTTPS/API URL
        return json.loads(response.read().decode("utf-8"))


def _metadata_url() -> str:
    custom = os.environ.get("OMNIFRAME_UPDATE_URL", "").strip()
    if custom:
        return custom
    return f"https://api.github.com/repos/{repo_slug()}/releases/latest"


def _latest_metadata(fetcher: FetchJSON) -> dict[str, Any]:
    url = _metadata_url()
    try:
        payload = fetcher(url)
    except HTTPError as exc:
        if exc.code != 404 or os.environ.get("OMNIFRAME_UPDATE_URL"):
            raise
        payload = fetcher(f"https://api.github.com/repos/{repo_slug()}/tags")

    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        raise ValueError("GitHub update metadata must be a JSON object")
    latest = payload.get("latest_version") or payload.get("version") or payload.get("tag_name")
    normalized = normalize_version(latest)
    if normalized is None:
        raise ValueError("GitHub update metadata did not contain a valid version")
    return {
        "latest_version": normalized,
        "release_url": payload.get("release_url") or payload.get("html_url"),
        "release_notes": payload.get("release_notes") or payload.get("body"),
    }


def _write_cache(path: Path, status: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".update-", delete=False
        ) as handle:
            json.dump(status, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as exc:
        LOG.debug("could not write update cache", extra={"path": str(path), "error": str(exc)})


def load_cached_update_status(
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    """Read a valid cached status without network access."""

    target = _cache_path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not data.get("current_version"):
        return None
    return data


def _status_base(*, now: float, source: str, error: str | None = None) -> dict[str, Any]:
    return {
        "current_version": normalize_version(__version__) or __version__,
        "latest_version": None,
        "update_available": False,
        "release_url": None,
        "release_notes": None,
        "repo_slug": repo_slug(),
        "checked_at": now,
        "source": source,
        "error": error,
    }


def check_for_update(
    *,
    force: bool = False,
    cache_path: str | os.PathLike[str] | None = None,
    fetcher: FetchJSON | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Check GitHub with cache/offline fallback; never raises for remote failures."""

    current_time = time.time() if now is None else float(now)
    target = _cache_path(cache_path)
    cached = load_cached_update_status(target)
    if not force and cached:
        try:
            age = max(0.0, current_time - float(cached.get("checked_at", 0)))
        except (TypeError, ValueError):
            age = _ttl_seconds() + 1
        if age < _ttl_seconds():
            result = dict(cached)
            result["source"] = "cache"
            result["error"] = None
            return result

    try:
        metadata = _latest_metadata(fetcher or _fetch_json)
        current = normalize_version(__version__) or __version__
        latest = metadata["latest_version"]
        result = {
            "current_version": current,
            "latest_version": latest,
            "update_available": compare_versions(latest, current) > 0,
            "release_url": metadata.get("release_url"),
            "release_notes": metadata.get("release_notes"),
            "repo_slug": repo_slug(),
            "checked_at": current_time,
            "source": "github" if fetcher is None else "mock",
            "error": None,
        }
        _write_cache(target, result)
        return result
    except Exception as exc:  # pragma: no cover - exact exception depends on network/runtime
        message = f"update check unavailable: {exc}"
        if cached:
            result = dict(cached)
            result["source"] = "cache"
            result["error"] = message
            return result
        result = _status_base(now=current_time, source="offline", error=message)
        _write_cache(target, result)
        return result


def get_cached_update_advisory(
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    """Return only a newer-version advisory from cache; never performs I/O over network."""

    status = load_cached_update_status(path)
    if not status or not status.get("update_available"):
        return None
    return {
        "current_version": status.get("current_version"),
        "latest_version": status.get("latest_version"),
        "release_url": status.get("release_url"),
        "release_notes": status.get("release_notes"),
        "source": status.get("source", "cache"),
        "upgrade_command": "omniframe self-update",
    }


def upgrade_command() -> list[str]:
    """Build the configured upgrade argv without invoking a shell."""

    configured = os.environ.get("OMNIFRAME_UPGRADE_COMMAND", "").strip()
    if configured:
        parsed = shlex.split(configured)
        if not parsed:
            raise ValueError("OMNIFRAME_UPGRADE_COMMAND is empty")
        return parsed
    package = f"omniframe-studio[ui] @ git+https://github.com/{repo_slug()}.git"
    return [sys.executable, "-m", "pip", "install", "--upgrade", package]


def _result_output(value: str | None) -> str:
    return (value or "")[-8000:]


def apply_update(
    status: dict[str, Any] | None = None,
    *,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Apply a known update with a shell-free subprocess and structured result."""

    resolved = status or check_for_update()
    if not resolved.get("update_available"):
        return {
            "success": True,
            "skipped": True,
            "reason": "no newer version is available or update status is offline",
            "current_version": resolved.get("current_version", __version__),
            "latest_version": resolved.get("latest_version"),
        }

    try:
        command = upgrade_command()
        execute = runner or subprocess.run
        completed = execute(
            command,
            capture_output=True,
            text=True,
            timeout=_timeout_seconds() * 10,
            check=False,
        )
        return {
            "success": completed.returncode == 0,
            "skipped": False,
            "returncode": completed.returncode,
            "stdout": _result_output(completed.stdout),
            "stderr": _result_output(completed.stderr),
            "current_version": resolved.get("current_version"),
            "latest_version": resolved.get("latest_version"),
        }
    except Exception as exc:
        return {
            "success": False,
            "skipped": False,
            "error": str(exc),
            "current_version": resolved.get("current_version"),
            "latest_version": resolved.get("latest_version"),
        }


def stream_update_events(
    status: dict[str, Any] | None = None,
    *,
    popen_factory: PopenFactory | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield safe progress events for an explicit update request."""

    resolved = status or check_for_update()
    yield {"event": "status", "status": resolved}
    if not resolved.get("update_available"):
        yield {
            "event": "completed",
            "success": True,
            "skipped": True,
            "message": "No newer version is available or update status is offline.",
        }
        return

    try:
        command = upgrade_command()
        yield {"event": "started", "executable": Path(command[0]).name}
        launch = popen_factory or subprocess.Popen
        process = launch(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if process.stdout is not None:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    yield {"event": "log", "line": line}
        returncode = process.wait()
        yield {
            "event": "completed",
            "success": returncode == 0,
            "skipped": False,
            "returncode": returncode,
        }
    except Exception as exc:
        yield {"event": "error", "success": False, "error": str(exc)}


def restart_instructions() -> dict[str, Any]:
    """Return explicit instructions for restarting the local UI process."""

    command = [sys.executable, "-m", "omniframe.cli", "ui", "--host", "127.0.0.1", "--port", "8765"]
    return {
        "restart_required": True,
        "command": shlex.join(command),
        "message": "Stop the current OmniFrame UI process, then run the command to load the updated package.",
    }
