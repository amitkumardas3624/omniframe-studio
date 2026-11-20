from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_posix_installer_has_safe_online_install_contract() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "set -euo pipefail" in text
    assert "gbd718106-cmyk/omniframe-studio.git" in text
    assert "OMNIFRAME_REPO_URL" in text
    assert "omniframe-studio[ui]" in text
    assert "doctor --json" in text
    assert "ffmpeg" in text.lower()
    assert "playwright" in text.lower()
    assert "shell=True" not in text


def test_powershell_installer_has_safe_online_install_contract() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "Set-StrictMode" in text
    assert "gbd718106-cmyk/omniframe-studio.git" in text
    assert "OMNIFRAME_REPO_URL" in text
    assert "omniframe-studio[ui]" in text
    assert "doctor --json" in text
    assert "ffmpeg" in text.lower()
    assert "playwright" in text.lower()
    assert "Invoke-Expression" not in text
