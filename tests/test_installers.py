from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_posix_installer_has_safe_online_install_contract() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "set -euo pipefail" in text
    assert "amitkumardas3624/omniframe-studio.git" in text
    assert "OMNIFRAME_REPO_URL" in text
    assert "omniframe-studio[ui]" in text
    assert "doctor --json" in text
    assert "ffmpeg" in text.lower()
    assert "playwright" in text.lower()
    assert "shell=True" not in text


def test_powershell_installer_has_safe_online_install_contract() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "Set-StrictMode" in text
    assert "amitkumardas3624/omniframe-studio.git" in text
    assert "OMNIFRAME_REPO_URL" in text
    assert "omniframe-studio[ui]" in text
    assert "doctor --json" in text
    assert "ffmpeg" in text.lower()
    assert "playwright" in text.lower()
    assert "Invoke-Expression" not in text


CANONICAL_SLUG = "amitkumardas3624/omniframe-studio"
STALE_SLUGS = ("gbd718106-cmyk/omniframe-studio", "omniframe-studio/omniframe-studio")
LIVE_SURFACES = (
    "install.sh",
    "install.ps1",
    "README.md",
    "SKILL.md",
    "pyproject.toml",
    "src/omniframe/updater.py",
    "src/omniframe/backend/server.py",
)


def test_canonical_repository_slug_is_the_only_one_referenced() -> None:
    """No surface may keep pointing at a stale repository identity."""

    for relative in LIVE_SURFACES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert CANONICAL_SLUG in text, relative
        for stale in STALE_SLUGS:
            assert stale not in text, f"{relative} still references {stale}"


def test_documentation_url_uses_the_repository_default_branch() -> None:
    """The `Documentation` URL must match the branch the installers fetch."""

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "tree/master/docs" in text
    assert "tree/main" not in text
