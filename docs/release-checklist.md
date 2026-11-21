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

## Release record — 0.2.0 (2026-11-22)

What was actually run for this release, and what it produced. The checklist above is the template;
this section is the evidence.

**Pre-release**

- [x] Repository identity resolved — canonical
      `https://github.com/amitkumardas3624/omniframe-studio`, propagated to every surface, with a
      drift guard in `tests/test_installers.py`.
- [x] `python -m compileall -q src` → exit 0.
- [x] `python -m pytest -q` → **362 passed, 1 skipped** (the host-dependent `bridge_host` test).
- [x] `ruff check src tests` → **All checks passed!** — the 95-error pre-existing debt was cleared
      in this release run, so the CI lint gate is green for the first time.
- [x] `pip install -e .` → exit 0; `pip install -e ".[dev]"` → exit 0; `omniframe --help` → exit 0.
- [x] Distribution built with `python -m build` (1.6.1): a wheel **and** an sdist. Wheel payload
      checked for `omniframe/py.typed` and `omniframe/agent/schemas/*.json`; sdist payload checked
      for `pyproject.toml`, `LICENSE` and `src/omniframe/py.typed`.
- [x] `python -m omniframe.cli doctor --json` → `"ready": true` on the build machine.
- [x] No proprietary DCC host claimed as tested — none is installed; `import_tested` and
      `production_candidate` are both **0**.

**During release**

- [x] Version bumped in `pyproject.toml` **and** `src/omniframe/__init__.py`: `0.1.0` → `0.2.0`.
- [x] Pre-release matrix re-run at the bumped version (results above are at 0.2.0).
- [x] Tag `v0.2.0` created on the release commit and pushed to `origin`.
- [x] Artifacts built: `omniframe_studio-0.2.0-py3-none-any.whl` (173,730 bytes) and
      `omniframe_studio-0.2.0.tar.gz` (198,211 bytes).
- [x] Checksums produced and published next to the files: `artifacts.sha256` (archive file digests,
      `sha256sum -c`-compatible) plus one per-archive entry sidecar for each artifact.

**Post-release**

- [x] Downloaded-artifact verification: the recorded archive digests were re-checked against
      `Get-FileHash` — both **MATCH**.
- [x] Fresh-environment install: the wheel was installed into a clean virtual environment;
      `import omniframe` → `0.2.0` and `omniframe --help` → exit 0. After adding the optional
      `render` extra and Chromium to that same clean environment, `doctor --json` reports
      `"ready": true` with only the optional native accelerator and the DCC hosts missing.
- [x] `docs/compatibility-matrix.md` updated with the exact machine and environment used for this
      verification; `render_tested` is claimed only for `h264`, `webm`/VP9 and `gif`, which were
      actually encoded and probed.
- [x] The release is recorded in `docs/phase-reports/phase5-release.md` (section *Release 0.2.0*).

**Still true after this release**

- No DCC host was verified: `import_tested` = 0, `production_candidate` = 0.
- The Phase-4 "server imports without fastapi" criterion is still unmet as literally written and is
  carried as a dependency declaration, not a waiver.

**Changed after this release**

- The "new CI jobs never ran on a hosted runner" limitation is **closed**: they ran on the tagged
  commit. The `install` jobs (6/6) and the `wheel` job passed; the `test` job failed on all three
  Python versions with a collection error because two pre-existing test modules imported the
  optional `fastapi` without a guard. Fixed in the follow-up commit by guarding both modules with
  `pytest.importorskip("fastapi")`, installing `".[dev,ui]"` in the `test` job so the UI tests
  actually run, and declaring the Starlette `TestClient` HTTP client in the `dev` extra.
- The published sdist still ships the two test modules in their pre-fix form; the library code in
  the artifacts is unaffected.
