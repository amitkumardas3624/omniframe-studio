# One-line installer for OmniFrame Studio on Windows PowerShell.
# Usage: irm https://raw.githubusercontent.com/gbd718106-cmyk/omniframe-studio/master/install.ps1 | iex
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoUrl = if ($env:OMNIFRAME_REPO_URL) {
    $env:OMNIFRAME_REPO_URL
} else {
    'https://github.com/gbd718106-cmyk/omniframe-studio.git'
}

function Write-Info([string]$Message) {
    Write-Host "[omniframe] $Message" -ForegroundColor Cyan
}

function Write-WarningMessage([string]$Message) {
    Write-Warning "[omniframe] $Message"
}

$pythonCommand = $null
$pythonArgs = @()
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pythonCommand = $python.Source
} else {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $pythonCommand = $pyLauncher.Source
        $pythonArgs = @('-3')
    }
}

if (-not $pythonCommand) {
    throw 'Python 3.10+ is required. Install it from https://www.python.org/downloads/ and rerun this command.'
}

$versionProbe = & $pythonCommand @pythonArgs -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}"); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10+ is required; found $versionProbe"
}
Write-Info "Using Python $versionProbe"

$hasPip = $true
& $pythonCommand @pythonArgs -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    $hasPip = $false
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
$packageSpec = "omniframe-studio[ui] @ git+$repoUrl"
if ($uv) {
    Write-Info "Installing OmniFrame Studio with uv from $repoUrl"
    & $uv.Source pip install --system $packageSpec
} elseif ($hasPip) {
    Write-Info "Installing OmniFrame Studio with pip from $repoUrl"
    & $pythonCommand @pythonArgs -m pip install $packageSpec
} else {
    throw 'Neither uv nor pip is available for this Python. Install pip (or uv) and rerun the installer.'
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-WarningMessage 'FFmpeg was not found. Video composition needs FFmpeg. Install it with winget install Gyan.FFmpeg or another trusted package manager.'
} else {
    Write-Info 'FFmpeg found.'
}

$playwrightProbe = @'
import importlib.util
from pathlib import Path
if importlib.util.find_spec("playwright") is None:
    raise SystemExit(2)
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
try:
    raise SystemExit(0 if Path(p.chromium.executable_path).exists() else 1)
finally:
    p.stop()
'@
& $pythonCommand @pythonArgs -c $playwrightProbe *> $null
$playwrightStatus = $LASTEXITCODE
if ($playwrightStatus -eq 2) {
    Write-WarningMessage "Playwright is not installed. Browser-backed rendering is optional; install it with: $pythonCommand -m pip install 'omniframe-studio[render]'"
} elseif ($playwrightStatus -ne 0) {
    Write-WarningMessage "Playwright is installed but Chromium is missing. Install it with: $pythonCommand -m playwright install chromium"
} else {
    Write-Info 'Playwright and Chromium are available.'
}

Write-Info 'Running OmniFrame Studio environment doctor'
& $pythonCommand @pythonArgs -m omniframe.cli doctor --json
Write-Info 'Installation complete. Start the UI with: omniframe ui --host 127.0.0.1 --port 8765'
