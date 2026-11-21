#!/usr/bin/env bash
# One-line installer for OmniFrame Studio on Linux and macOS.
# Usage: curl -fsSL https://raw.githubusercontent.com/amitkumardas3624/omniframe-studio/master/install.sh | bash
set -euo pipefail

REPO_URL="${OMNIFRAME_REPO_URL:-https://github.com/amitkumardas3624/omniframe-studio.git}"

info() {
  printf '\033[1;36m[omniframe]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[omniframe warning]\033[0m %s\n' "$*" >&2
}

fail() {
  printf '\033[1;31m[omniframe error]\033[0m %s\n' "$*" >&2
  exit 1
}

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python}"
else
  fail "Python 3.10+ is required. Install Python from https://www.python.org/downloads/ and rerun this command."
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  fail "Python 3.10+ is required; found: $($PYTHON_BIN --version 2>&1)"
fi

HAS_PIP=0
if "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  HAS_PIP=1
fi

if command -v uv >/dev/null 2>&1; then
  info "Installing OmniFrame Studio with uv from ${REPO_URL}"
  uv pip install --system "omniframe-studio[ui] @ git+${REPO_URL}"
elif [ "$HAS_PIP" -eq 1 ]; then
  info "Installing OmniFrame Studio with pip from ${REPO_URL}"
  "$PYTHON_BIN" -m pip install "omniframe-studio[ui] @ git+${REPO_URL}"
else
  fail "Neither uv nor pip is available for this Python. Install pip (or uv) and rerun the installer."
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  warn "FFmpeg was not found. Video composition needs FFmpeg. Install it with your OS package manager (for example: brew install ffmpeg or apt install ffmpeg)."
else
  info "FFmpeg found: $(ffmpeg -version 2>/dev/null | head -n 1)"
fi

if ! "$PYTHON_BIN" -c 'import importlib.util; raise SystemExit(0 if importlib.util.find_spec("playwright") else 1)' >/dev/null 2>&1; then
  warn "Playwright is not installed. Browser-backed rendering is optional; install it with: ${PYTHON_BIN} -m pip install \"omniframe-studio[render]\""
elif ! "$PYTHON_BIN" -c 'from pathlib import Path; from playwright.sync_api import sync_playwright; p = sync_playwright().start(); ok = Path(p.chromium.executable_path).exists(); p.stop(); raise SystemExit(0 if ok else 1)' >/dev/null 2>&1; then
  warn "Playwright is installed but Chromium is missing. Install it with: ${PYTHON_BIN} -m playwright install chromium"
else
  info "Playwright and Chromium are available."
fi

info "Running OmniFrame Studio environment doctor"
"$PYTHON_BIN" -m omniframe.cli doctor --json
info "Installation complete. Start the UI with: omniframe ui --host 127.0.0.1 --port 8765"
