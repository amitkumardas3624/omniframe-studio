# OmniFrame Phase 0 Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the known action-contract drift, pytest module collision and raw-checkout import failure while preserving the current runtime behavior.

**Architecture:** The runtime `ActionRegistry.to_json_document()` remains the canonical action contract. The committed `src/omniframe/agent/schemas/tools.json` becomes a generated snapshot checked against that runtime contract. Example audio tests load their target file under a unique module name instead of mutating `sys.path`, and pytest/CI run from the `src/` layout without manual environment setup.

**Tech Stack:** Python 3.10+, pytest 8+, Typer CLI, JSON, setuptools, GitHub Actions, optional ruff/mypy.

## Global Constraints

- Preserve Python `>=3.10` support and the existing `src/` package layout.
- Keep Pillow fallback and optional dependencies unchanged.
- Keep FFmpeg invocation argument-list based; never use `shell=True`.
- Do not patch proprietary binaries or bypass DRM.
- Do not overwrite existing user files, untracked work or generated outputs.
- Do not commit changes unless the user explicitly authorizes commits.
- Do not silently choose a canonical GitHub repository URL when the local remote, installer URL and user-provided URL disagree; surface the mismatch for explicit resolution.

---

### Task 1: Add regression coverage for the action manifest and audio import isolation

**Files:**
- Create: `tests/test_tool_manifest_consistency.py`
- Modify: `tests/test_omniframe_promo_audio.py:1-8`
- Test fixture: `src/omniframe/agent/schemas/tools.json`

**Interfaces:**
- Consumes: `ensure_builtin_actions()` and `ActionRegistry.to_json_document()` from `omniframe.core.agent_runtime.actions` / `registry`.
- Produces: a deterministic test contract requiring the committed manifest to equal the runtime manifest, and a unique module import for the promo audio generator.

- [ ] **Step 1: Write the failing manifest consistency test**

Create a test that loads the committed JSON and compares it with the runtime document:

```python
import json
from pathlib import Path

from omniframe.core.agent_runtime.actions import ensure_builtin_actions


MANIFEST = Path(__file__).parents[1] / "src/omniframe/agent/schemas/tools.json"


def test_committed_tool_manifest_matches_runtime():
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runtime = ensure_builtin_actions().to_json_document()
    assert committed == runtime
```

Add a second assertion that the runtime action names are exactly the expected current set:

```python

def test_current_builtin_action_names_are_stable():
    assert ensure_builtin_actions().names() == [
        "bridge.detect",
        "bridge.generate_script",
        "bridge.inspect",
        "bridge.list",
        "checkpoint.diff",
        "checkpoint.list",
        "checkpoint.restore",
        "checkpoint.save",
        "compose.video",
        "engine.route",
        "environment.detect",
        "inspect.frames",
        "inspect.media",
        "project.report",
        "project.translate",
        "project.validate",
        "render.cartoon_frames",
        "render.code_scene",
        "timeline.diff",
    ]
```

- [ ] **Step 2: Run the manifest test and confirm the expected failure**

Run:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q tests/test_tool_manifest_consistency.py
```

Expected: the committed manifest or its description differs from the runtime registry because the current snapshot still declares 18 actions while the runtime exposes 19.

- [ ] **Step 3: Replace `sys.path` mutation in the promo audio test**

Replace the current import block with a file-location import that has a unique module identity:

```python
import importlib.util

PROMO_AUDIO = Path("examples/omniframe-promo/generate_audio.py").resolve()
spec = importlib.util.spec_from_file_location("omniframe_promo_generate_audio", PROMO_AUDIO)
assert spec is not None and spec.loader is not None
promo_audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promo_audio)
generate_bed = promo_audio.generate_bed
```

Do not insert either example directory into `sys.path`. This prevents `generate_audio` from the handwashing example from remaining in pytest’s module cache and being reused by the promo test.

- [ ] **Step 4: Run the focused audio tests and confirm they pass**

Run:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q tests/test_omniframe_promo_audio.py tests/test_handwashing_project.py tests/test_handwashing_render.py
```

Expected: all focused tests pass, including the 30-second promo frame-count assertion.

---

### Task 2: Regenerate the committed action manifest from the runtime

**Files:**
- Modify: `src/omniframe/agent/schemas/tools.json`
- Inspect only: `src/omniframe/core/agent_runtime/registry.py:268-300`
- Inspect only: `src/omniframe/cli/main.py:214-235`
- Test: `tests/test_tool_manifest_consistency.py`

**Interfaces:**
- Consumes: `omniframe tools --out <path>` and `ActionRegistry.to_json_document()`.
- Produces: a committed manifest whose `schema_version`, `kind`, tool names, schemas and metadata match the runtime.

- [ ] **Step 1: Generate the manifest using the existing CLI**

Run from the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m omniframe.cli tools --out src/omniframe/agent/schemas/tools.json
```

Do not hand-edit individual action entries. The runtime registry is the source of truth.

- [ ] **Step 2: Run the consistency test**

Run:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q tests/test_tool_manifest_consistency.py
```

Expected: the manifest equality test and the stable-name test pass.

- [ ] **Step 3: Confirm the count through independent surfaces**

Run:

```powershell
$env:PYTHONPATH = 'src'
python -c "from omniframe.core.agent_runtime.actions import ensure_builtin_actions; r=ensure_builtin_actions(); print(len(r.names()))"
python -m omniframe.cli tools --list
```

Expected: the first command prints `19`, and the second prints exactly the 19 names listed in Task 1.

---

### Task 3: Correct the agent documentation contract and stale examples

**Files:**
- Modify: `AGENT_GUIDE.md:17`
- Modify: `src/omniframe/agent/AGENT_GUIDE.md:14-44`
- Modify: `README.md` only where it states a stale action count
- Test: `tests/test_tool_manifest_consistency.py`

**Interfaces:**
- Consumes: the generated runtime action names from Task 2.
- Produces: documentation that uses real action identifiers and directs agents to runtime discovery rather than stale hard-coded examples.

- [ ] **Step 1: Add documentation assertions that expose the current drift**

Extend `tests/test_tool_manifest_consistency.py` with:

```python
ROOT_GUIDE = Path(__file__).parents[1] / "AGENT_GUIDE.md"
AGENT_GUIDE = Path(__file__).parents[1] / "src/omniframe/agent/AGENT_GUIDE.md"


def test_guides_do_not_claim_eighteen_actions_or_stale_action_names():
    text = ROOT_GUIDE.read_text(encoding="utf-8") + AGENT_GUIDE.read_text(encoding="utf-8")
    assert "18-action" not in text
    assert "all 18 actions" not in text
    assert "project.render" not in text
    assert "project.compose" not in text
```

Run the test and confirm it fails against the current guides.

- [ ] **Step 2: Update the root quick reference**

Replace the `full 18-action registry` wording with a runtime-discovery instruction:

```text
For the current action registry, run `omniframe tools --list` or inspect `src/omniframe/agent/schemas/tools.json`.
```

- [ ] **Step 3: Update the detailed agent guide examples**

Use the actual action identifiers:

```python
result = call_action("render.code_scene", {
    "html": "<div id='scene'></div>",
    "output_dir": "out/render",
})

result = call_action("compose.video", {
    "frames_dir": "out/render",
    "output": "out/video.mp4",
})
```

Replace the stale `project.render` and `project.compose` examples. Update the tool-list description to say “the current generated tool manifest” rather than a fixed count.

- [ ] **Step 4: Run the documentation consistency test**

Run:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q tests/test_tool_manifest_consistency.py
```

Expected: all manifest and documentation assertions pass.

---

### Task 4: Make raw-checkout pytest execution independent of manual `PYTHONPATH`

**Files:**
- Modify: `pyproject.toml:61-69`
- Create: `.github/workflows/ci.yml`
- Test: the complete `tests/` suite

**Interfaces:**
- Consumes: the existing setuptools `src/` layout and pytest configuration.
- Produces: a repository where `python -m pytest -q` works after the documented editable install, and CI always performs that install explicitly.

- [ ] **Step 1: Add the pytest source path configuration**

Add this key inside `[tool.pytest.ini_options]`:

```toml
pythonpath = ["src"]
```

Keep `testpaths`, `addopts`, markers and warning filters unchanged.

- [ ] **Step 2: Add a minimal CI workflow**

Create `.github/workflows/ci.yml` with a matrix for Python 3.10, 3.11 and 3.12. Each job must:

1. check out the repository;
2. set up the matrix Python version;
3. install the project with `python -m pip install -e ".[dev]"`;
4. run `python -m compileall -q src`;
5. run `python -m pytest -q`;
6. run `python -m ruff check src tests` when ruff is installed by the dev extra.

The workflow must not execute proprietary hosts and must report render tests according to their existing markers.

- [ ] **Step 3: Run the complete suite from the raw checkout**

Run in a fresh PowerShell process:

```powershell
python -m pytest -q
```

Expected: collection succeeds without `ModuleNotFoundError`. If the audio test still fails, return to Task 1 rather than weakening its duration assertion.

- [ ] **Step 4: Run the compile and lint checks**

Run:

```powershell
python -m compileall -q src
python -m ruff check src tests
```

Expected: exit code 0 for both commands. If a pre-existing lint error is found, record the exact file/line and fix only errors introduced or exposed by this phase.

---

### Task 5: Record repository identity without guessing the canonical remote

**Files:**
- Create: `docs/repository-identity.md`
- Modify: `README.md` only if the user-approved canonical URL is known
- Modify: `pyproject.toml` only if the user-approved canonical URL is known
- Test: `tests/test_repository_identity.py` only after a canonical URL is explicitly selected

**Interfaces:**
- Consumes: local `git remote -v`, README installer URL, `pyproject.toml` project URLs and the user-provided public repository URL.
- Produces: a bounded identity report; no automatic URL rewrite based on an unconfirmed guess.

- [ ] **Step 1: Create the identity report**

Record the currently observed values:

```markdown
# Repository identity

- User-provided public repository: `https://github.com/amitkumardas3624/omniframe-studio`
- Local configured remote: `https://github.com/gbd718106-cmyk/omniframe-studio.git`
- README installer source: `https://github.com/gbd718106-cmyk/omniframe-studio`
- pyproject project URLs: `https://github.com/omniframe-studio/omniframe-studio`
- Canonical release source: unresolved; do not silently rewrite until explicitly selected.
```

- [ ] **Step 2: Run the metadata inspection**

Run:

```powershell
git remote -v
python -c "from pathlib import Path; print(Path('pyproject.toml').read_text(encoding='utf-8'))"
```

Expected: the report matches the current checkout and clearly states that the URLs are inconsistent.

- [ ] **Step 3: Do not change URLs without explicit source selection**

Leave the existing URL values unchanged in this phase unless the user separately identifies the canonical release repository. This prevents publishing installers or package metadata to the wrong project.

---

### Task 6: Phase 0 acceptance gate

**Files:**
- Inspect: all files changed in Tasks 1–5
- Test: complete test, compile and lint commands

**Interfaces:**
- Consumes: all Phase 0 changes.
- Produces: a written phase report with pass/fail status and unresolved repository identity blocker.

- [ ] **Step 1: Run the complete verification set**

```powershell
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -m omniframe.cli doctor --json
python -c "from omniframe.core.agent_runtime.actions import ensure_builtin_actions; r=ensure_builtin_actions(); print('ACTION_COUNT', len(r.names()))"
```

- [ ] **Step 2: Check the acceptance criteria**

The gate passes only if:

- package collection has no `ModuleNotFoundError`;
- full pytest has zero failures;
- promo audio test sees 30 seconds and handwashing tests see 10 seconds;
- manifest and guides agree with 19 runtime actions;
- compile and lint checks pass;
- doctor output is recorded with unavailable optional hosts clearly separated from core readiness;
- repository identity mismatch is documented and not silently rewritten.

- [ ] **Step 3: Write the phase report**

Create `docs/phase-reports/phase0-correctness.md` containing the exact commands, exit codes, test counts, known skips, changed files and remaining identity decision. Do not describe Phase 0 as complete if any acceptance item fails.

## Handoff to later phases

After this plan’s gate passes, create and review separate plans for:

1. rendering/compositor hardening;
2. durable local jobs and safety;
3. bridge interoperability;
4. UI and agent experience;
5. packaging and release hardening.

Each later plan must name exact files and acceptance tests after re-inspecting the current post-Phase-0 code. Do not pre-commit to stale line numbers or unverified host behavior.
