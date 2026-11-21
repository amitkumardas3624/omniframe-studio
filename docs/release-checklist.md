# OmniFrame Release Checklist

This checklist is the human-facing companion to the release tooling in
`src/omniframe/release/`. It applies to every public or download-facing release of
OmniFrame Studio. The checks are deliberately ordered: identity before tagging,
matrix before shipping, and verification after announcing.

> **Prerequisite — repository identity: RESOLVED 2026-11-22.** Phase 0 recorded a
> mismatch between the canonical repository URL and what the installers/`pyproject.toml`
> referenced (see `docs/repository-identity.md`). The user named
> `https://github.com/amitkumardas3624/omniframe-studio` as canonical (the GitHub
> username change left the old slug behind), and it is now propagated to the git
> remote `origin`, `install.ps1`, `install.sh`, `README.md`, `SKILL.md`, the
> `pyproject.toml` `[project.urls]` block, the updater's default repo slug, and the
> server's fallback link. `tests/test_installers.py` now fails if any of those
> surfaces drifts back to a stale slug.
>
> The rule still stands for the future: if a mismatch appears again, **stop and ask** —
> never silently rewrite a URL to "fix" it, and never publish while the surfaces
> disagree.

## 1. Pre-release

- [x] Repository-identity blocker resolved — canonical
      `https://github.com/amitkumardas3624/omniframe-studio` (see prerequisite above
      and `docs/repository-identity.md`).
- [ ] Run the full test matrix on a clean checkout:
      `python -m compileall -q src`
      `python -m pytest -q`
      `python -m ruff check src tests`
- [ ] Run the install matrix: `pip install -e .` (no extras) and
      `pip install -e ".[dev]"`, then `omniframe --help` must exit 0.
- [ ] Build the distribution and confirm the wheel ships `py.typed` and
      `agent/schemas/*.json` (the CI `wheel` job does this; run it manually
      before a local-only release).
- [ ] Run `python -m omniframe.cli doctor --json` and confirm `"ready": true`
      with capabilities that match the machine you are about to bless.
- [ ] Confirm no proprietary DCC host is claimed as tested unless it was
      actually present on a test machine (`docs/compatibility-matrix.md`).

## 2. During release

- [ ] Bump the version in `pyproject.toml` and `src/omniframe/__init__.py`
      together (`tests/test_install_matrix.py::test_package_version_matches_metadata`
      enforces the two stay in sync).
- [ ] Re-run the pre-release matrix once more at the bumped version.
- [ ] Create and push the release tag (only after the identity blocker is
      resolved and the user authorized publishing).
- [ ] Build the artifacts that users will download (wheel/sdist).
- [ ] Checksum them for the release announcement:
      `python -c "from omniframe.release.sign import checksum_archive; import sys; print(checksum_archive(sys.argv[1]))" dist/*.whl`
      and publish the produced `artifacts.sha256` sidecar next to the files.

## 3. Post-release

- [ ] Verify a downloaded artifact with the published sidecar:
      `sha256sum -c artifacts.sha256` (Linux/macOS) or compare `Get-FileHash`
      output by hand (Windows).
- [ ] Install the downloaded artifact into a fresh environment and run
      `python -m omniframe.cli doctor --json`; record the output.
- [ ] Update `docs/compatibility-matrix.md` with the exact machine/env used for
      the verification, and mark the produced files as `render_tested` only
      where they were actually produced and probed.
- [ ] Record the release in the phase reports ledger (see
      `docs/phase-reports/phase5-release.md` for the consolidated readiness
      summary).
- [ ] Update `docs/release-checklist.md` if any step above changed (this file
      is a living document; the checklist must never lie about what was run).

## Honesty rules

- `generated` / `structurally_checked` / `import_tested` / `render_tested` /
  `production_candidate` are distinct levels; never promote a level without the
  evidence that level requires.
- A host that was not installed on any test machine is `unverified` for that
  machine, no matter how confident the code looks.
- The checksum sidecar is the *only* promise that the announced bytes are the
  shipped bytes; do not publish an artifact without one.