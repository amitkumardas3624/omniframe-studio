# Phase 5 — Packaging and Release Hardening — Gate Report

Date: 2026-11-21
Workspace: `.worktrees/omniframe-platform-hardening` (branch `omniframe-platform-hardening`, all uncommitted)
Plan: `docs/superpowers/plans/2026-11-21-omniframe-phase5-release.md`

## Outcome: GATE PASS — engineering scope, identity blocker resolved

Every Phase-5 engineering task is implemented and verified: the cross-platform install/test matrix,
the job-DB schema migration path, reproducible artifact checksums with a written release checklist,
and an evidence-based compatibility matrix feeding this production-readiness report.

The one **release-blocking** issue — the **repository identity** mismatch, raised in Phase 0 and
carried through Phases 1–5 — was **resolved on 2026-11-22**: the user named
`https://github.com/amitkumardas3624/omniframe-studio` as the canonical release source (the cause
was a GitHub username change), and it was propagated to every surface. Details in
*Repository identity — raised, then resolved*.

Also recorded, not waived: one Phase-4 checklist sentence is still not satisfied as literally written
(the backend imports `fastapi`/`pydantic` unconditionally). Phase 5 declared those frameworks
instead of pretending the import was optional — see *Carried Phase-4 deviation*.

Verification levels in this report are the narrow ones the plan defines. Nothing here was executed
on a machine with Premiere Pro, After Effects, DaVinci Resolve, CapCut or Krita installed; no codec
was claimed as working that was not actually encoded and probed in Phase 5. The Phase-0..5 work was
committed and pushed on 2026-11-22 with the user's authorization: first to the
`omniframe-platform-hardening` branch, then fast-forwarded into `master` (a pure fast-forward —
`origin/master` was an ancestor, so no history was rewritten).

---

## Phase 5 task summary

| # | Task | Files | Verdict |
|---|------|-------|---------|
| 1 | Cross-platform install/test matrix | `src/omniframe/py.typed` (new), `pyproject.toml` (`dev` extra: `tomli` for <3.11), `.github/workflows/ci.yml` (`install`, `wheel` jobs, additive), `tests/test_install_matrix.py` (new, 18 tests) | PASS |
| 2 | Schema migrations | `src/omniframe/migrations/{__init__,registry}.py` (new), `src/omniframe/jobs/store.py` (DDL ownership moved), `src/omniframe/core/errors.py` (`+MigrationError`), `tests/test_migrations.py` (new, 18 tests) | PASS |
| 3 | Reproducible artifacts + checklist | `src/omniframe/release/sign.py` (new), `src/omniframe/release/__init__.py` (new), `docs/release-checklist.md` (new), `tests/test_release_artifacts.py` (new, 15 tests) | PASS |
| 4 | Compatibility matrix + readiness report | `src/omniframe/release/compat.py` (new), `docs/compatibility-matrix.md` (new), `tests/test_compat.py` (new, 20 tests), this report | PASS |

71 new Phase-5 tests. Phase 4 collected 290 (289 passed, 1 skipped); the tree now collects 361.

---

## Task 1 — Cross-platform install/test matrix

`src/omniframe/py.typed` was declared in `[tool.setuptools.package-data]` but did not exist, so the
distribution advertised PEP 561 typing without shipping the marker. Created, empty except one newline
(a *complete* marker; `partial\n` would be a different claim).

`pyproject.toml` `dev` extra gained `tomli>=2.0; python_version < "3.11"`, because the install-matrix
test reads `tomllib` (3.11+ stdlib) and the suite is meant to run from the `dev` extra.

`.github/workflows/ci.yml` extended additively — the pre-existing `test` job (3.10/3.11/3.12,
`compileall`, `pytest`, `ruff`) is untouched — with:

- `install`: matrix `python-version` × `extras: ["", "[dev]"]`, `pip install -e ".$extras"`,
  `python -c "import omniframe; print('OMNIFRAME_IMPORT_OK', omniframe.__version__)"`, `omniframe --help`.
- `wheel`: `python -m pip wheel . --no-deps -w dist`, then a `python - <<'PY'` heredoc that opens the
  wheel with `zipfile` and asserts `omniframe/py.typed` and `agent/schemas/*.json` are inside
  (`python -m build` is not installed and is not a declared dev dependency; `pip wheel` is the accepted
  substitution the plan allows).

Caught while writing it: the unquoted step name `Install project (extras: ${{
matrix.extras }})` broke YAML — the `: ` made GitHub's parser read a mapping (`ScannerError: mapping values
are not allowed here`). Quoted the step name, then validated the file parses.

`tests/test_install_matrix.py` (18 passed, ruff clean) pins what a future edit could silently break:
metadata files exist; `omniframe.__version__` equals the `pyproject` version; `requires-python` floors at
`>=3.10` with no upper cap; **core** dependencies are host-free (`pydantic`, `pyyaml`, `typer`, `pillow`
present; `playwright`, `fastapi`, `uvicorn`, `pybind11`, `pytest`, `ruff`, `mypy` absent) while
`render`/`ui`/`native`/`dev` extras carry them; the `tomli` marker is `< 3.11`; console scripts
`omniframe` → `omniframe.cli.main:run` and `mcp` → `omniframe.mcp_server:main` both resolve to a
callable reachable by **AST walk** (the modules are not imported, so the test does not need the optional
framework); `py.typed` is listed as package-data, exists, and is not `partial`; `agent/schemas/*.json` is
package-data and `tools.json` has a non-empty `tools` list; the `src` layout is declared properly and no
stray root `omniframe/` exists; the build backend is `setuptools.build_meta`; the CI matrix covers
3.10/3.11/3.12 and `extras: ["", "[dev]"]`; and the workflow never launches a proprietary host
binary (`premiere`/`afterfx`/`resolve`/`capcut`/`krita`).

**Limitation, recorded not hidden:** the workflow has never run on a live GitHub runner. Its evidence is
YAML parsing plus static and local checks of the same commands. The plan asked for this to be noted here.

---

## Task 2 — Schema migrations

`src/omniframe/migrations/registry.py`:

- guard table `schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)`, created
  outside the transaction so a re-open can always read it;
- frozen `Migration(version, name, statements)`; `MIGRATIONS = (Migration(1, "base_job_schema", (BASE_JOBS_SCHEMA,)),)`;
- `current_version(db_path)` — `0` for a missing file, **no side effect** (it does not create the DB);
- `apply_migrations(db_path, *, to_version=None)` — validates the target before touching disk (an unknown
  target leaves no file behind), refuses downgrades, applies ascending inside `BEGIN IMMEDIATE`, records
  `(version, applied_at)` per step, and rolls back with `MigrationError` on `sqlite3.Error`; it also refuses
  a DB whose guard table names a version this build does not know ("written by a newer OmniFrame").

`in-memory` (`:memory:`) and `file:` URIs are rejected loudly with `ValidationError`: a migration that
cannot be inspected or rolled back is not a migration.

`JobStore` no longer owns DDL. `_init_schema()` calls `apply_migrations(self.db_path)`, so the migrations
module is the single owner of the job schema and the previous `_SCHEMA` block is gone rather than
duplicated. Additive `MigrationError(OmniFrameError)` with `code = "E_MIGRATION"` — the error taxonomy is
append-only, so no existing code discriminates on a new value.

`tests/test_migrations.py` (18 passed) covers the chain being ordered, unique and dense; fresh DB → latest;
`current_version` not creating files; nested parent dirs; idempotent re-apply with `applied_at` unchanged and
exactly one row per version; ISO timestamps with a timezone; the exact `jobs` column set; unknown and
non-int target rejection before disk contact; a corrupt DB raising the documented `OmniFrameError`
with its 42 bytes preserved byte-for-byte; `:memory:`/URI rejection; a v2 row from a hypothetical newer
build being refused; `JobStore` opening at latest and reopening without rewriting `applied_at`; and
— via a monkeypatched two-migration registry — ascending application order, downgrade refusal and
new-table creation.

Frozen compatibility: the 20 existing job tests (`test_jobs_store.py` 10, `test_jobs_manager.py` 10)
still pass unchanged.

---

## Task 3 — Reproducible artifacts and release checklist

`checksum_archive(archive_path, *, algorithm="sha256", sidecar=None, write_sidecar=True)` returns
`{"archive", "algorithm", "entry_count", "entries" (sorted), "sidecar"}` and writes an `artifacts.sha256`
sidecar in `sha256sum` format (`<hex>  <name>\n`, sorted), UTF-8 with `newline="\n"` so the bytes match on
Windows and Linux.

Reproducibility choices that the tests pin: entries are sorted; `./` prefixes and backslashes are
normalised (`sample/a.txt` == `./sample/a.txt`) because tar and zip disagree; directory entries are skipped;
detection uses `zipfile.is_zipfile` rather than the suffix (so a mislabelled archive is handled correctly);
and files stream through `CHUNK_SIZE = 1 MiB` hashes, so a payload larger than one chunk is hashed
correctly without being read whole.

`tests/test_release_artifacts.py` (15 passed): two archives with different mtimes and inconsistent member
order produce **identical** digests; the same archive twice is identical; the sidecar has no `\r`, is
newline-terminated, its line count equals `entry_count`, and parsing it reproduces the returned report;
zip and tar of the same tree agree; directories are excluded; missing/non-archive files and unknown
algorithms raise `ValidationError`.

`docs/release-checklist.md` is written in pre/during/post-release order, with the identity question as an
explicit prerequisite box in pre-release, and states the rules this report is meant to obey — do not
promote a verification level, do not claim an uninstalled host works, do not publish an artifact without
its sidecar. It also notes that the version lives in two places
(`pyproject.toml` and `src/omniframe/__init__.py` `__version__`) and must be bumped together, which
`test_install_matrix.py` enforces.

---

## Task 4 — Compatibility matrix

`compatibility_report(env, presets=None, *, probe=None, evidence=None)` reports, per preset, the container,
video/audio codec, transparency support, and two **separate** fields:

- `capability` — what the local ffmpeg *build* offers: `encoder_present`, `encoder_missing` or `unknown`,
  read from `ffmpeg -hide_banner -encoders`;
- `status` — what was **actually demonstrated** here: `unverified`, `import_tested` or `render_tested`.

The split is the honesty mechanism. Being listed in `-encoders` is a capability, not evidence, and it never
promotes `status`. A codec becomes `render_tested` only if OmniFrame's own preset encoded a real 16×16,
3-frame synthetic clip and `ffprobe` could read back a `codec_type: video` stream. `import_tested` stays
reserved for artifacts actually imported and stays **0** in this phase.

Measured on this machine (the report was executed, not hand-written — `summary`:
`{"unverified": 4, "import_tested": 0, "render_tested": 3}`):

| Preset | capability | status | reason |
|--------|-----------|--------|--------|
| `h264` | encoder_present | render_tested | encoded 1623 bytes, `codec_name='h264'` |
| `webm` (VP9) | encoder_present | render_tested | encoded 617 bytes, `codec_name='vp9'` |
| `gif` | encoder_present | render_tested | encoded 957 bytes, `codec_name='gif'` |
| `prores` | encoder_present | unverified | no artifact produced and probed in this phase |
| `qtrle_alpha` | encoder_present | unverified | same; present in the build is not evidence |
| `png_sequence` | encoder_present | unverified | same |
| `h265` | encoder_missing | unverified | build's encoder is named `libx265`; nothing encoded |

The `h265` row is the clearest case for keeping the two fields apart: the report would have been wrong in
either direction if it had collapsed them — "supported" because HEVC is mainstream, or "broken" because a
name lookup missed. It says the encoder name this build exposes is not the one probed, and that nothing was
encoded. That is all that was observed.

---

## Acceptance gate checklist (run from worktree root)

```
$env:PYTHONPATH='src'
python -m compileall -q src
python -m pytest -q
ruff check src tests
python -c "from omniframe.release.compat import compatibility_report; ..."
python -m omniframe.cli doctor --json
```

### `python -m compileall -q src`
Exit 0. `py.typed`, the two new packages (`migrations`, `release`) and every touched module compile.

### `python -m pytest -q` (full suite)
```
360 passed, 1 skipped in 104.20s
```
Exit 0. The counts reconcile: Phase 4 recorded 290 collected; Phase 5 adds 71
(18 install-matrix + 18 migrations + 15 release-artifacts + 20 compatibility) for 361 total. The single
skip is the pre-existing host-dependent `bridge_host` test, unchanged since Phase 3 — it is still a skip
because no DCC host is installed, not because it was disabled.

Per-module Phase-5 evidence captured during the phase:

| Module | Tests | Command result |
|--------|-------|----------------|
| `tests/test_install_matrix.py` | 18 | `18 passed` |
| `tests/test_migrations.py` | 18 | `18 passed` |
| `tests/test_jobs_store.py` + `test_jobs_manager.py` (frozen) | 20 | `20 passed` after the JobStore rewire |
| `tests/test_release_artifacts.py` | 15 | `15 passed` |
| `tests/test_compat.py` | 20 | `20 passed` |

### `ruff check src tests`
```
Found 95 errors.
```
Pristine baseline from `HEAD` (`6749271`), measured with `git archive` + `Expand-Archive`, same ruff
0.17.6, same untouched config:

```
Found 97 errors.
```

**Net −2.** Every Phase-5 file is individually clean:

```
src\omniframe\release\compat.py           All checks passed!
src\omniframe\release\sign.py             All checks passed!
src\omniframe\release\__init__.py         All checks passed!
src\omniframe\migrations\registry.py      All checks passed!
src\omniframe\migrations\__init__.py      All checks passed!
tests\test_compat.py                      All checks passed!
tests\test_migrations.py                  All checks passed!
tests\test_release_artifacts.py           All checks passed!
tests\test_install_matrix.py              All checks passed!
```

The −2 was not engineered by deleting debt: the phase added files and removed one duplicated DDL block
(store `_SCHEMA` → migrations `BASE_JOBS_SCHEMA`), which happened to drop two `E501`-class long lines. The
remaining 95 are pre-existing debt recorded by Phases 0–4; the CI lint gate stays red until that is
cleared, and this phase is not the place it clears.

> **Superseded during the 0.2.0 release run.** The pre-existing debt was cleared afterwards, so
> `ruff check src tests` now reports `All checks passed!` (0 errors) and the CI lint gate is green.
> The figures above record the state **at the Phase-5 gate**, which is what this report measured.
> See *Release 0.2.0* below for the cleanup and what it changed.

### `compatibility_report({"machine": "probe"})`
Ran; `summary` = `{"unverified": 4, "import_tested": 0, "render_tested": 3}`; per-preset values as in the
table above. Host-free: no DCC host is touched at all.

### `python -m omniframe.cli doctor --json`
```
ready: true
platform: Windows 11 (11.0.26300), AMD64, CPython 3.12.10
python            available  3.12.10
node              available  v24.14.0
ffmpeg/ffprobe    available  8.1.1-full_build-www.gyan.dev
chromium          available  151.0.7922.34   (source: playwright)
native_accelerator unavailable  No module named 'omniframe._native._omniframe_native'
premiere_pro / after_effects / davinci_resolve / capcut / krita   all unavailable
```

`ready: true` with the five DCC hosts in `missing` is the intended split: OmniFrame's own compose/render
path is ready, host interop is unverified because there is nothing to verify against.

---

## Repository identity — raised, then resolved

Phase 0 recorded three different repositories for one project (`docs/repository-identity.md`):

| Surface | Value found |
|---------|-------|
| User-provided public repository | `github.com/amitkumardas3624/omniframe-studio` |
| Git remote `origin` + both installers + README | `github.com/gbd718106-cmyk/omniframe-studio` |
| `pyproject.toml` project URLs | `github.com/omniframe-studio/omniframe-studio` |

Plus a branch drift: the `Documentation` URL pointed at `tree/main` while the repository's default
branch is `master`.

This was **release-blocking**: a release publishes installers and package metadata that tell users where
to fetch and trust the source. If any one of those surfaces is wrong, users are pointed at a repository
that does not control the release — and a wrong `Homepage`/`Issues` URL is exactly the shape of a
supply-chain-looking mistake. Only the operator could decide which URL is authoritative; a guess would
have been a silent rewrite of provenance, which the plan forbids and no test can validate. Nothing was
rewritten while it was open.

**Resolution (2026-11-22).** The user named
`https://github.com/amitkumardas3624/omniframe-studio` as canonical and explained the cause: a GitHub
username change left the old slug behind. That URL was propagated to every surface:

| Surface | Change |
|---------|--------|
| git remote `origin` (fetch + push) | `git remote set-url origin https://github.com/amitkumardas3624/omniframe-studio.git` |
| `install.sh` | usage comment + default `REPO_URL` |
| `install.ps1` | usage comment + default `$repoUrl` |
| `README.md`, `SKILL.md` | both one-line install commands |
| `pyproject.toml` `[project.urls]` | `Homepage`, `Documentation`, `Issues` |
| `pyproject.toml` `Documentation` branch | `tree/main` → `tree/master` |
| `src/omniframe/updater.py` | `DEFAULT_REPO_SLUG` → `amitkumardas3624/omniframe-studio` |
| `src/omniframe/backend/server.py` | fallback "Web UI not yet built" link |
| `tests/test_installers.py` | assertions updated **+ a new drift guard** |

The guard matters more than the edit: `tests/test_installers.py` now fails if any live surface keeps a
stale slug (`gbd718106-cmyk/…` or `omniframe-studio/omniframe-studio`), omits the canonical one, or
points `Documentation` at `tree/main` — so the same class of drift cannot silently return.

Remote state was verified, not assumed: `git ls-remote origin` resolves the new repository, and its
`master` (4759e40) is an ancestor of the local `master` — i.e. the old slug was the same project under
the old username, so the new remote is a fast-forward away rather than a divergent history.

---

## Carried Phase-4 deviation

Phase 4's checklist line *"server imports without fastapi installed (guarded)"* is **not satisfied as
written**, and Phase 5 resolved the ambiguity rather than the sentence:

- `src/omniframe/backend/server.py:27-29` imports `fastapi` (and `fastapi.middleware.cors`,
  `fastapi.responses`) at module level, and `JobSubmit` extends `pydantic.BaseModel` at line 102.
- What *is* import-guarded is the optional Phase-2 subsystem, `omniframe.jobs` (`server.py:343-347`); without
  it the app still constructs, exposes no `/api/v1/jobs*` routes, and the Jobs panel shows
  "jobs unavailable".

`fastapi`, `pydantic` and `uvicorn` are declared in the `ui` extra, and the backend is a declared subsystem,
so "import the backend without fastapi" is not a supported configuration — the sentence mispairs a required
framework with an optional subsystem. The corrected statement is: **optional subsystems are import-guarded;
required frameworks are declared.** The core install stays host-free and framework-free, and
`test_install_matrix.py` pins that (fastapi/uvicorn/pydantic absent from core dependencies). A genuinely
fastapi-free `import omniframe.backend.server` would need lazy framework import, deferred `BaseModel`
definitions and guarded decorators; it was **not** attempted.

---

## Verification-level honesty statement

This report distinguishes what the plan distinguishes, and does not upgrade anything by prose:

- **`generated`** — files exist and were written by this work.
- **`structurally_checked`** — code compiled (`compileall` exit 0), linted, and asserted structurally by
  tests that never launch an external host. CapCut fixtures are here and stop here.
- **`import_tested`** — an artifact was imported by a host and accepted. **Count: 0.** No DCC host is
  installed on this machine, so no bridge artifact can hold this level.
- **`render_tested`** — OmniFrame encoded the media and `ffprobe` read it back. **Count: 3**
  (`h264`, `webm`/VP9, `gif`). This says nothing about whether Premiere, Resolve or CapCut would accept the
  file.
- **`production_candidate`** — **Count: 0**, and none is claimed. Not available from this machine at all.

Consequently no host is claimed as working: `premiere_pro`, `after_effects`, `davinci_resolve`, `capcut` and
`krita` are `available: false` in `doctor`, and every row in `docs/compatibility-matrix.md` for them is
"runbook only, not executed". The bridge code paths are exercised against fixtures, which is why the
bridge phase could pass; host-success claims remain untestable here and are not made.

Scope note, unchanged from earlier phases: OmniFrame is an agent-orchestration, rendering, composition,
interchange and bridge platform — not a reimplementation of a proprietary NLE. Cloning a proprietary
application's full behaviour is explicitly out of scope for the platform, so "parity with Premiere/CapCut"
is not a goal that could be verified or denied here.

---

## Earlier phase gates — all passed

| Phase | Report | Outcome |
|-------|--------|---------|
| 0 | `phase0-correctness.md` | PASS (correctness scope), two deferred items recorded |
| 1 | `phase1-rendering.md` | GATE PASS — 5/5 tasks, independent verifiers |
| 2 | `phase2-jobs-safety.md` | GATE PASS — 4/4 tasks, independent verifiers |
| 3 | `phase3-bridges.md` | GATE PASS — 4/4 tasks, plus the JobManager race fix |
| 4 | `phase4-ui.md` | GATE PASS — with one documented wording deviation (carried above) |
| 5 | this file | GATE PASS — engineering scope; identity blocker resolved |

Phase 0's deferred items were the pre-existing lint debt and CI redness; both were recorded in every
subsequent report and not regressed to (−2 net at Phase 5). **Both were later cleared** — the lint debt
during the 0.2.0 release run (see *Release 0.2.0*), which also turned the CI lint gate green.

---

## Release 0.2.0 — 2026-11-22

The first tagged release of OmniFrame Studio. Version `0.1.0` → `0.2.0`, bumped together in
`pyproject.toml` and `src/omniframe/__init__.py` (the sync is enforced by
`tests/test_install_matrix.py::test_package_version_matches_metadata`).

**Why 0.2.0 and not 1.0.0.** The platform is still pre-1.0: no proprietary DCC host was verified on
any machine, and the CI matrix had not yet run on a hosted runner when this was tagged — its first
hosted run happened as part of this release and found three defects (see *CI on a hosted runner*). The
minor bump reflects the new subsystems and the lint cleanup; it does not claim production readiness.

### Lint debt cleared: 95 → 0

The tree-wide lint debt (95 errors against a 97-error pristine baseline) was the last red gate. It is
now **0 errors**, so the pre-existing CI `test` job's lint step can pass.

- 74 of the 95 were ruff's own safe auto-fixes: unused imports, import sorting, `typing.Dict`/`List`
  → builtin generics, `Optional[X]` → `X | None`, deprecated `typing` imports, quoted annotations;
- the remaining 18 were fixed by hand: `zip(..., strict=False)` where the original `zip` behaviour had
  to be preserved, `raise ... from exc`, an unused loop variable renamed, an unused local removed, the
  `Backend.close` optional hook documented, and the ten `%`-format call sites in the bridge generators
  rewritten as f-strings.

**One real bug fixed on the way.** The Premiere Pro bridge generator emitted its `CLIPS` entries with
**doubled braces** (`{{ track: 0, ... }}`) — leftover escaping from an earlier template — which is a
JavaScript syntax error in the generated ExtendScript file, while every other object literal in the
same file used single braces. The rewrite to f-strings corrected it. It was caught by generating the
bridge scripts before and after the change and diffing them byte for byte: the `after_effects` and
`davinci_resolve` outputs were byte-identical, and the only Premiere difference was the two `CLIPS`
lines.

**One test adjusted.** `tests/test_zero_reencode.py` monkeypatched `ffprobe_info` on the compositor
module, but that module never used the name (it was a dead re-export) — the live call path is
`ffmpeg.ffprobe_info`. The patch is now `raising=False`, with a comment saying so.

### Packaging metadata modernised

`project.license` moved from the deprecated TOML table to the SPDX string `"MIT"`, the deprecated
`License ::` classifier was dropped, and the build requirement moved to `setuptools>=77` (the first
release that emits `License-Expression`). The wheel now carries `Metadata-Version: 2.4`,
`License-Expression: MIT` and `License-File: LICENSE`, and the build emits no deprecation warnings.

### Artifacts

| File | Size | Contents verified |
|------|------|-------------------|
| `omniframe_studio-0.2.0-py3-none-any.whl` | 173,730 bytes | 73 entries; `omniframe/py.typed` present; `omniframe/agent/schemas/*.json` present |
| `omniframe_studio-0.2.0.tar.gz` | 198,211 bytes | 144 entries; `pyproject.toml`, `LICENSE` and `src/omniframe/py.typed` present |

Built with `python -m build` (1.6.1) — **both** a wheel and a real sdist, which closes the Phase-5
limitation that only `pip wheel` was available.

### Checksums

- `artifacts.sha256` — sha256 of the two **archive files**, in `sha256sum` format, so a downloader can
  run `sha256sum -c artifacts.sha256` against the bytes they received. Verified here against
  `Get-FileHash`: both **MATCH**.
- `omniframe_studio-0.2.0-py3-none-any.whl.sha256` / `omniframe_studio-0.2.0.tar.gz.sha256` —
  per-entry digests of the contents inside each archive, produced by
  `omniframe.release.sign.checksum_archive` (73 and 123 entries).

### Verification at 0.2.0

- `python -m compileall -q src` → exit 0
- `python -m pytest -q` → **362 passed, 1 skipped** (the host-dependent `bridge_host` test)
- `ruff check src tests` → **All checks passed!** (0 errors)
- `pip install -e .` and `pip install -e ".[dev]"` → exit 0; `omniframe --help` → exit 0;
  `OMNIFRAME_IMPORT_OK 0.2.0`
- `compatibility_report` → `{"unverified": 4, "import_tested": 0, "render_tested": 3}` (unchanged)
- `omniframe doctor --json` → `ready: true` on the build machine (ffmpeg + Chromium present)

**Fresh-environment install (post-release check).** The built wheel was installed into a clean virtual
environment: `import omniframe` → `0.2.0`, `omniframe --help` → exit 0. `doctor` in that bare
environment reports `ready: false` **only** because a default install has no Chromium — the optional
`render` extra (playwright) is not part of the core dependency set, and the `ready` flag requires both
ffmpeg and Chromium. After adding `playwright` and `playwright install chromium` to that same clean
environment, `doctor --json` reports **`ready: true`**, with only the optional native accelerator and
the five DCC hosts listed as missing. That closes the loop: the published artifact installs and comes
up ready on a machine that is provisioned the way the installer scripts provision it.

### Published release

| Fact | Value |
|------|-------|
| Tag | `v0.2.0` (annotated), pointing at commit `f7626db` |
| Release | <https://github.com/amitkumardas3624/omniframe-studio/releases/tag/v0.2.0> (published, not a draft, not a pre-release) |
| Assets | the wheel, the sdist, `artifacts.sha256`, and one per-archive entry sidecar for each archive |

Archive digests, as published:

```
626743ac45037ae61bd44351d3fd979397249021871569bb4f8fca221e285413  omniframe_studio-0.2.0-py3-none-any.whl
2fabfe78def4e6bed9c7143fb518b2eaa6c2b997f0466f0f6f1ea3d1c43625ff  omniframe_studio-0.2.0.tar.gz
```

**Downloaded-artifact verification.** The assets were downloaded back from the published release and
checked against the published `artifacts.sha256`: both **MATCH**. The downloaded wheel was then
unpacked and all **73** of its entries were checked against the published per-archive sidecar: **73
matched, 0 problems**. Finally the *downloaded* wheel was installed into a clean virtual environment
(`import omniframe` → `0.2.0`, `omniframe --help` → exit 0), and after adding the optional `render`
extra and Chromium, `doctor --json` reports **`ready: true`**.

### CI on a hosted runner — and the defects it exposed

This release is the first time the workflow ran on a real GitHub runner, so the "never executed on a
hosted runner" limitation is now closed. During the 0.2.0 work it ran **nine** times: twice before the
tag, seven times from the tag onward. Three defects had to be fixed on the way, none of them visible
locally, and two of them real bugs in the library.

The two hosted runs *before* the tag matter to the claim, so they are in the table: `install` 6/6 and
`wheel` were green there too, and `test` was red on all three versions with the same collection error
the tag then carried. In other words the tag was not the workflow's first contact with a runner, and
the "never ran on a hosted runner" debt was already closed when it was cut.

**Defect 1 — two test modules imported the optional UI framework unguarded** (`491a427`). On the
tagged commit `f7626db`:

- `install` (3.10/3.11/3.12 × no-extras/`[dev]`) — **6/6 passed**
- `wheel` — **passed**
- `test` (3.10/3.11/3.12) — **failed on all three**, with a *collection* error, not a test failure:

```
ERROR collecting tests/test_ui_server.py
ERROR collecting tests/test_update_api.py
E   ModuleNotFoundError: No module named 'fastapi'
```

This is exactly the pre-existing debt Phase 4 recorded — *"tests/test_ui_server.py — no
`importorskip` guard"* — except that `tests/test_update_api.py` had it too. The `test` job installs
only `.[dev]`, and `fastapi` lives in the `ui` extra, so two test modules imported an optional
framework without a guard and the whole collection aborted before a single test ran. The library code
was never exercised as broken; the suite could not even be collected.

**Fixed in the follow-up commit** (on `master`, after the tag):

- both modules now use `pytest.importorskip("fastapi")` like their sibling UI test modules, so a
  suite without the optional framework **skips** instead of erroring;
- the `test` job installs `".[dev,ui]"`, so the UI tests are no longer skipped in CI — they run;
- the HTTP client that Starlette's `TestClient` needs is now **declared**: `httpx>=0.27,<0.29`, plus
  `httpx2>=2.0.0` for Python ≥ 3.11 (Starlette 1.10 prefers `httpx2`; older Starlette uses `httpx`).
  It was previously undeclared — the UI tests only worked locally because an unrelated package
  happened to pull it in — and the marker keeps the 3.10 CI job installable.

That fixed collection, but not the job. Two more red runs followed, and each exposed a defect the
local suite could not see because it runs on Windows.

**Defect 2 — the streaming encoder never collected FFmpeg's exit status** (`4ebc7ea`). Run
`44942830309` got past collection and failed four tests in `tests/test_streaming_pipeline.py` on
3.10, 3.11 and 3.12 alike:

```
ValueError: flush of closed file
  .../subprocess.py:2067: in _communicate
    self.stdin.flush()
```

`RawVideoStream.close()` closed the stdin pipe to signal end-of-stream, then called
`Popen.communicate()` — which flushes `Popen.stdin` itself before waiting, and flushing an
already-closed file raises. The
POSIX `_communicate` only catches `BrokenPipeError` there; the Windows implementation takes a
different path, which is why the same four tests passed locally every time. The user-visible consequence is
not cosmetic: every streamed render (`CodeVideoRenderer.render(stream_to_ffmpeg=...)`,
`render_frames(stream_to_ffmpeg=...)`) raised a bare `ValueError` on Linux and macOS instead of
returning, and the real FFmpeg stderr — the thing `RenderError` exists to carry — was thrown away.

The handle is now detached (`process.stdin = None`) right after the pipe is closed, inside a
`finally` so a failing `close()` cannot leave it attached. EOF still reaches FFmpeg and the exit
status is still collected. `test_close_detaches_stdin_before_communicate` pins this without an FFmpeg
binary: a fake process flushes its stdin the way CPython does, and the test verifies the pre-fix
sequence raises while the current one returns `rc=0`.

**Defect 3 — a cancel could lose to the worker's failure record** (`a87057b`). Run `44945420622`
was green on 3.11 and 3.12 and red on 3.10 alone, in
`tests/test_ui_jobs.py::test_submit_and_cancel_job_via_http`:

```
AssertionError: job 355f85b7... did not reach ['canceled'];
last={... 'status': 'failed', 'error': "no worker registered for job kind 'validate'..."}
```

The HTTP surface had answered 200 with `canceled`; polling the same job returned `failed`. This is
not a test-ordering complaint — it is a lifecycle race in `JobManager`. `cancel()` wrote `canceled`
with no coordination with the worker, and the worker's "no registered callable" path wrote `failed`
without ever consulting the cancel flag. Whoever wrote last won, so a job the caller had withdrawn
could be resurrected as a queue malfunction. The same commit passed in a second run
(`44946942008`), which is what a race looks like when it is reported as flaky.

Lifecycle writes now share one lock: `cancel()` sets the flag and records `canceled` under it, the
claim (read + `running`) runs under it, and both terminal paths re-check the flag before recording
`failed` or `done`. `test_cancel_wins_over_a_missing_worker` submits and cancels the
stock-kind-without-a-worker job 20 times; against the pre-fix code it failed in 4 of 5 local runs, and
after the fix it has not failed once.

**Run-by-run history**, so the green claim is auditable rather than cheerful:

| Run | Commit | `install` | `wheel` | `test` |
|---|---|---|---|---|
| `44938110155` | `a330be2` (before the tag) | 6/6 | pass | fail — `fastapi` collection error, ×3 |
| `44938278540` | `b2376dd` (before the tag) | 6/6 | pass | fail — same error, ×3 |
| `44941271851` | `f7626db` (the tag) | 6/6 | pass | fail — `fastapi` collection error, ×3 |
| `44942289090` | `491a427` | 6/6 | pass | fail — 10 tests, ×3 |
| `44942830309` | `5bdd203` | 6/6 | pass | fail — closed stdin, ×3 |
| `44945420622` | `4ebc7ea` | 6/6 | pass | fail — cancel race, 3.10 only |
| `44946942008` | `4ebc7ea` | 6/6 | pass | pass — same commit, race won |
| `44947420899` | `a87057b` | 6/6 | pass | **pass ×3** |
| `44949858877` | `a036a67` (docs) | 6/6 | pass | **pass ×3** |

The `a87057b` row is the gate: all ten jobs success, on 3.10, 3.11 and 3.12. The row below it is the
same ten jobs for the docs commit that introduced this section — a docs-only push, so it confirms
rather than assumes that recording the history did not disturb the suite.

**What the published artifacts contain.** The `v0.2.0` tag points at `f7626db`, so the published
wheel and sdist carry the pre-fix form of both library defects above: a streamed render on POSIX
raises `ValueError: flush of closed file` instead of returning, and a canceled queued job can be
overwritten as `failed` by the worker. Both fixes are on `master` after the tag (`4ebc7ea`,
`a87057b`) and belong in the next release. The sdist additionally ships the two test modules in
their `fastapi`-unguarded form. The tag's own release notes stay as written — they describe what was
verified at `f7626db` — but nothing should cite this tag as a CI-verified build.

---

## Known debt, deliberately not touched

1. `src/omniframe/backend/server.py` — legacy typing (`Dict`/`List`/`Optional`), two unsorted import blocks,
   dead imports (`subprocess`, `uuid`, `concurrent.futures.*`), one unused local (`result`). Pre-existing;
   left alone so the phase diff stays honest. **Cleared during the 0.2.0 release run.**
2. Tree-wide lint debt: 95 errors against a 97-error pristine baseline. The pre-existing `test` CI job
   fails on it and will keep failing until someone owns a cleanup phase. **Cleared during the 0.2.0
   release run: 0 errors.**
3. `tests/test_ui_server.py` — no `importorskip` guard (pre-existing). **Resolved during the 0.2.0
   release run: both `test_ui_server.py` and `test_update_api.py` now `importorskip("fastapi")`, and
   the `test` job installs `.[dev,ui]` so they run rather than skip there.**
4. The new CI `install`/`wheel` jobs have never run on a hosted runner (local YAML/static evidence only).
   **Closed during the 0.2.0 release run: they ran on the tagged commit and on every follow-up, and
   all ten jobs are green at `a87057b` (run `44947420899`).**
5. `python -m build` is unavailable here; `pip wheel . --no-deps -w dist` is the accepted substitute, so
   nothing in this phase proves an sdist builds. **Resolved during the 0.2.0 release run: `build` was
   installed and a real sdist was produced and verified.**
6. Optional DCC hosts are absent, so bridge work is fixture-level (`bridges/*.py` runbook paths unexecuted).
7. Aikido security-scan tooling was unavailable in this session; the repo has not been scanned by it, and
   that is recorded rather than implied clean.
8. The Phase-0..5 work was uncommitted until the user authorized commit + push on 2026-11-22; it now
   lives on both `master` and `omniframe-platform-hardening` at the same commit. See
   *Repository identity — raised, then resolved* for the branch and remote used.

---

## How to reproduce

```powershell
cd .worktrees/omniframe-platform-hardening
$env:PYTHONPATH='src'
python -m compileall -q src
python -m pytest -q
$ruff='C:\Users\AK ANIK\AppData\Local\Temp\omniframe-ruff-verify\Scripts\ruff.exe'
& $ruff check src tests
python -c "from omniframe.release.compat import compatibility_report; print(compatibility_report({})['summary'])"
python -m omniframe.cli doctor --json
```

---

## Next

Phase 0–5 gates all pass on engineering scope, the repository-identity question is resolved (canonical
source named by the user on 2026-11-22 and propagated to every surface), `0.2.0` is tagged and published,
and the workflow has now run on a hosted runner with all ten jobs green at `a87057b`.

What that hosted run changed about "what remains": a real sdist is no longer unproven, and CI is no
longer only static evidence — but it also found two shipped defects, so the next release is not
optional housekeeping:

1. **`0.2.1` should ship `4ebc7ea` and `a87057b`.** The `v0.2.0` artifacts on the release page contain both
   library defects described above. They are fixed on `master`; cutting a release is what puts the
   fixes in front of anyone installing from PyPI or from the GitHub release page, and it is the only
   honest way to stop the "CI-verified" claim from being attached to an artifact that is not.
2. **Verify a DCC host.** `import_tested` is still 0 and `production_candidate` still 0 for every
   bridge; until one host is actually launched against the bridge entry points, those numbers stay
   where they are and this report keeps saying so.
3. **Run the security scan.** The Aikido scan is still a gap (item 7 above), recorded rather than
   assumed clean.

Full proprietary application cloning remains explicitly out of scope.
