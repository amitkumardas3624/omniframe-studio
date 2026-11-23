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

- The "new CI jobs never ran on a hosted runner" limitation is **closed**, and the full matrix is
  green at `a87057b` (run `44947420899`): six `install` jobs, `wheel`, and `test` on 3.10, 3.11 and
  3.12. It took five runs after the tag and three fixes to get there — the two runs before it were
  already red; the full run table, in order, is in
  `docs/phase-reports/phase5-release.md` under *CI on a hosted runner*.
- `491a427` (tests, workflow and packaging metadata only): `tests/test_ui_server.py` and
  `tests/test_update_api.py` guard the optional framework with `pytest.importorskip("fastapi")`, the
  `test` job installs `".[dev,ui]"` plus an FFmpeg step so those tests run rather than skip, and the
  Starlette `TestClient` HTTP client is declared in the `dev` extra instead of being borrowed from an
  unrelated package.
- `4ebc7ea` (library): `RawVideoStream.close()` closed the stdin pipe and then called
  `Popen.communicate()`, which flushes that same handle on POSIX and raised
  `ValueError: flush of closed file`. Every streamed render raised instead of returning on Linux and
  macOS, and FFmpeg's own stderr never reached `RenderError`. The handle is now detached after the
  pipe is closed; EOF and the exit status are unchanged for FFmpeg.
- `a87057b` (library): `JobManager` settles its lifecycle writes under one lock, so `cancel()` can no
  longer be overwritten by the worker's `done` / `failed` record, or by the "no worker registered"
  failure it writes for a stock kind with no callable.
- **The published `v0.2.0` wheel and sdist were built at `f7626db`, before all three commits.** The
  wheel's library code therefore contains both defects; the sdist additionally ships the two
  unguarded test modules. The release notes remain accurate as a record of what was verified at that
  commit, but this tag must not be cited as a CI-verified build. A follow-up release is the honest way
  to ship the fixes.

That follow-up shipped the same day; see *Release record — 0.2.1* below.

## Release record — 0.2.1 (2026-11-22)

The 0.2.0 record above ends by naming a follow-up release the honest way to ship the fixes. This is
that release, and its scope is deliberately small: the two library defects, and nothing else in the
library.

**What changed in the library**

- `4ebc7ea` — `RawVideoStream.close()` closes the stdin pipe to signal end-of-stream, detaches the
  handle (`process.stdin = None`) inside a `finally`, and only then calls `communicate()`. POSIX
  `_communicate` flushes `Popen.stdin` itself, so the old order raised
  `ValueError: flush of closed file` on every streamed render on Linux and macOS, and FFmpeg's real
  stderr never reached `RenderError`.
- `a87057b` — `JobManager` settles job lifecycle writes under one lock: `cancel()` sets its flag and
  records `canceled` under it, the claim (read + `running`) runs under it, and both terminal paths
  re-check the flag before recording `failed` or `done`. A withdrawn job can no longer be resurrected
  as `failed` by a worker that lost the race.

Everything else in the range is listed here so nobody has to diff it out of the release notes
themselves: `491a427` (the optional UI framework is guarded with `pytest.importorskip` in both test
modules, `test` installs `.[dev,ui]`, and the Starlette client dependency is declared instead of
borrowed) and `5bdd203` (hosted-Linux portability for the test suite). Neither changes library behaviour,
and neither is claimed as a feature.

**Pre-release**

- [x] Version bumped in `pyproject.toml` and `src/omniframe/__init__.py` together, `0.2.0` → `0.2.1`,
      and each re-read with `tomllib` / `importlib` afterwards rather than by eye.
- [x] `python -m compileall -q src` → exit 0.
- [x] `python -m pytest -q` → **364 passed, 1 skipped in 93.18s**. The skip is the host-dependent
      `bridge_host` test, the same one 0.2.0 skipped.
- [x] `ruff check src tests` → **All checks passed!** 0.2.0 cleared the 95-error baseline; this run is
      the check that the bump did not reintroduce any of it.
- [x] Wheel payload: **15 checks, 15 OK** — `omniframe/py.typed`, the agent tool schemas, the detached
      stdin handle in `raw_stream.py`, the lifecycle lock in `jobs/manager.py`, and in `METADATA` both
      `Version: 0.2.1` and the SPDX `License-Expression: MIT`.
- [x] Sdist payload: `pyproject.toml`, `LICENSE`, `py.typed`, `PKG-INFO` at `0.2.1`, and
      `pytest.importorskip("fastapi")` present in both `tests/test_ui_server.py` and
      `tests/test_update_api.py`.

Note on the metadata check: `METADATA` and `PKG-INFO` are written with CRLF line endings, so a plain
substring search for `Version: 0.2.1` fails on the carriage return. The first pass of this check
reported a false failure for exactly that reason; it normalises line endings before matching.

**During release**

- [x] Release commit `1562cdf` (`release: OmniFrame Studio 0.2.1`). Fast-forward push only; `master`
      and `omniframe-platform-hardening` both move to it, and the two remote refs are confirmed equal
      with `ls-remote` rather than assumed.
- [x] Annotated tag `v0.2.1` on `1562cdf` (tag object `e5d5c2d`), pushed by name and confirmed with
      `ls-remote` plus a local peel back to `1562cdf`.
- [x] CI checked **before** publishing, not after: run `44957685418` on `1562cdf`, conclusion `success`,
      **10 of 10** jobs — `wheel`, `test` on 3.10, 3.11 and 3.12, and six `install` jobs.
- [x] Artifacts built with `python -m build` (build 1.6.1): `omniframe_studio-0.2.1-py3-none-any.whl`
      (**174,219** bytes, 73 entries) and `omniframe_studio-0.2.1.tar.gz` (**199,689** bytes, 123 files;
      the tarball has 144 members because it also carries 21 directory entries).
- [x] Checksums published next to the files: `artifacts.sha256` (202 bytes, two lines, LF-terminated,
      `sha256sum -c`-compatible) plus one entry sidecar per archive, generated from the built archives
      themselves:

```
7b84476323d90b33a9a6b16993f4aeb044a6b6330c3db4fb7fde9ea921b396bb  omniframe_studio-0.2.1-py3-none-any.whl
195cc38c38f66475413f188ff51ef4ffbd1b5d003220d838dad93cf57d0e0420  omniframe_studio-0.2.1.tar.gz
```

- [x] Sidecars: `.whl.sha256` 7,332 bytes and 73 lines; `.tar.gz.sha256` 15,089 bytes and 123 lines. The
      sdist sidecar covers the 123 files, not the 21 directory entries, which is why its line count is
      below the tarball's member count; the verification below compares it against files only.
- [x] Five assets on the release page: the wheel, the sdist, `artifacts.sha256`, and the two sidecars.

**Post-release**

- [x] All five assets downloaded again from the published release page into an empty directory, so
      nothing already in `dist/` could stand in for the published bytes.
- [x] Archive digests computed from the downloaded bytes matched the published `artifacts.sha256`
      **and** the digest GitHub reports for each asset: two independent sources, both **MATCH** for
      both files.
- [x] Per-entry verification of the downloaded archives against the published sidecars: wheel **73 of
      73**, sdist **123 of 123**; 0 missing, 0 extra, 0 mismatched; `PROBLEMS=0`.
- [x] Fresh virtual environment (CPython 3.12.10, Windows 11) installed from the downloaded wheel:
      `import omniframe` → `0.2.1`, and `python -m omniframe.cli --help` → exit 0.
- [x] `doctor --json` in that environment **before** installing the extras → `"ready": false`, with
      `chromium` the only missing capability. Recorded as run, not smoothed over.
- [x] Then `pip install "<downloaded wheel>[render]"` and `python -m playwright install chromium` →
      `"ready": true`, Chromium `159.0.8154.6`, and `missing` reduced to `native_accelerator` plus the
      five DCC hosts.
- [x] Recorded in `docs/phase-reports/phase5-release.md` under *Superseded the same day by `v0.2.1`*,
      and this section pushed with it.

**Still true after this release**

- No DCC host was verified: `import_tested` = 0 and `production_candidate` = 0 for every bridge. The
  doctor output above is evidence in the honest direction — it lists five hosts as missing because this
  machine has none of them installed.
- The Aikido security scan has still not been run (0.2.0 record, debt item 7); recorded as a gap, not as
  a pass.
- The Phase-4 "server imports without `fastapi`" criterion is still unmet as literally written, and is
  still carried as a dependency declaration rather than a waiver.
- `doctor --json` reaches `"ready": true` only with the `render` extra and Chromium present. A plain
  install of `0.2.1` still reports `ready: false` with `chromium` missing. That is the intended
  optional-encoder design, and it is stated here so the `true` in the release notes is not read as a
  claim about the bare install.

**Changed after this release**

- `v0.2.0` is superseded and stays published as the record of what was built at `f7626db`. No tag was
  moved, no release deleted, no force push. Its artifacts still carry both library defects and the
  unguarded test modules; install `0.2.1` instead.
- The "CI-verified build" claim is now available, and it attaches to `v0.2.1` only. The timing, because
  this is the whole point of the exercise: the workflow run on `1562cdf` was created at `22:37:08Z` and
  finished green at `22:38:34Z`; the release object was created at `22:37:06Z` and **published** at
  `22:48:37Z`. `gh release create` creates the release as a draft, uploads the assets, then publishes
  it, so `publishedAt` is the timestamp that says when anyone could first see it. Both are given so the
  ordering can be checked rather than believed.
- `docs/compatibility-matrix.md` still records **362** tests from the 0.2.0 gate. It is a dated gate
  record and was left as written; this run reports 364 passed and 1 skipped.

Every local check in this record ran on Windows 11 (build `10.0.26300`) with CPython 3.12.10, `build`
1.6.1, and `ruff` from a throwaway virtual environment. The hosted half of the evidence above is
GitHub's `ubuntu-latest` runner.
