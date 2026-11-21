# OmniFrame Phase 3 — Bridge Interoperability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every professional-host bridge provable without ever claiming a host was tested when it was not. Add host-independent fixtures, a loss report for translation/inspection, an explicit verification-level contract, and version-aware fixtures (CapCut), plus acceptance runbooks for Adobe/Resolve that are executed only on hosts that actually exist here (currently none of Premiere/AE/Resolve/CapCut/Krita is installed on this machine — see doctor).

**Architecture:** Bridges already share `ToolBridge` with `BridgeTier` (`documented_api|reverse_engineered|ui_automation`), `BridgeReport`, `GeneratedScript`, `detect()`, `capabilities()`, `inspect()` and `generate_script()`. This phase strengthens that tier with fixtures that exercise the *generation and inspection* paths without opening the proprietary host, and records an honest verification level per fixture/test.

**Tech Stack:** Python 3.10+, Pydantic, pytest, existing `src/omniframe/bridges/*`. No proprietary host downloads; no DRM/patch.

## Global Constraints

- Preserve `src/` layout and the existing `ToolBridge` contract (do not break `get_bridge`/`list_bridges`).
- `detect()` must answer even when the host is missing (already does).
- Never mark a fixture/host-test as `production_candidate` or `render_tested` when the host was not opened and executed.
- No `shell=True`; argument-list only.
- Do not commit unless the user authorizes commits.

## Pre-inspection note

This machine's doctor shows `premiere_pro`, `after_effects`, `davinci_resolve`, `capcut`, `krita` all **not installed**. Therefore every bridge test in this phase must be host-independent (fixtures drive `generate_script`/`inspect`), and host-acceptance runbooks are *written* and marked "not executed — host absent", never claimed as run. That is a hard honesty boundary.

---

### Task 1: Host-independent bridge fixtures

**Files:**
- Create: `tests/fixtures/bridges/` (small golden fixture dirs/files)
- Create: `tests/test_bridges_fixtures.py`
- Inspect only: `src/omniframe/bridges/capcut.py`, `src/omniframe/bridges/premiere_pro.py`, `src/omniframe/bridges/after_effects.py`

**Interfaces:**
- Consumes: `generate_script(project, output_dir)` for at least CapCut, Premiere and AE (each returns `GeneratedScript` with `.path`, `.language`, `.metadata`, `.warnings`).
- Produces: a fixture-driven test that generates each bridge's script into `tmp_path` and asserts it is a non-empty file with the bridge's `script_extension`, and that `GeneratedScript.warnings` are empty (or explicitly expected).

- [ ] **Step 1** — For each of the three bridges, build a minimal in-memory `project` (Pydantic model) that satisfies `generate_script`'s expectations; generate into `tmp_path`.
- [ ] **Step 2** — Assert: `GeneratedScript.path` exists, `language` matches the bridge (`js`, `py`, etc.), `summary` non-empty, `metadata` serialisable. Keep them deterministic.
- [ ] **Step 3** — Re-run an existing bridge surface test: `python -m pytest -q tests/test_bridges.py` to confirm no regression and that `get_bridge("capcut").detect().installed is False` still holds.

---

### Task 2: Translation/inspection loss report

**Files:**
- Create: `src/omniframe/bridges/loss.py`
- Modify (optional, additive only): `src/omniframe/bridges/base.py` — add a `record_loss(...)` helper that bridges may call
- Test: create `tests/test_bridges_loss.py`

**Interfaces:**
- Produces: `LossReport` dataclass mapping each translated feature to `(supported, degraded, unsupported)` with reasons, and `LossReport.to_dict()`.

Example:
```python
@dataclass
class LossItem:
    feature: str
    status: str                 # supported | degraded | unsupported
    reason: str = ""

@dataclass
class LossReport:
    bridge: str
    total: int
    items: list[LossItem]
    def to_dict(self) -> dict: ...
    def summary(self) -> dict: count by status
```

`inspect()` (the default reverse-engineering probe) should produce a `LossReport`-style `"loss"` key (empty/degraded narrative) when a target cannot be fully understood — additive only, never breaking existing consumers that read `report["magic_ascii"]` etc.

- [ ] **Step 1** — Implement `loss.py` with `LossItem`/`LossReport`.
- [ ] **Step 2** — Extend `tool_base.inspect()` default output with an optional `"loss"` dict when it truncates (entry cap) or cannot read a known field; do not raise.
- [ ] **Step 3** — Tests: a non-empty `LossReport` serialises; `summary()` counts by status; inspect of a directory >500 entries includes the `loss`/`truncated` marker.

---

### Task 3: Verification levels bound to fixtures

**Files:**
- Create: `tests/test_bridges_verification.py`
- Inspect only: `src/omniframe/engines/code_video/renderer.py` (reuse `verification_level` from Phase 1)

**Interfaces:**
- Produces: a single source of truth macro in test, mapping each bridge test to one of `generated | structurally_checked | import_tested | render_tested | production_candidate`.

- [ ] **Step 1** — Tag every bridge fixture test with `generated` or `structurally_checked` (the file parses / structure checks), never `render_tested` for an absent host.
- [ ] **Step 2** — Add a pytest marker `@pytest.mark.bridge_host` used only when a real host is opened; here none exist, so the marker's tests are `skip`d with reason "host not installed".
- [ ] **Step 3** — Assert in `tests/test_bridges_verification.py` that no fixture test claims `render_tested`, and document the marking convention in `pyproject.toml` markers (add `bridge_host`).

---

### Task 4: CapCut version fixtures and Adobe/Resolve runbooks

**Files:**
- Inspect only: `src/omniframe/bridges/capcut.py` (see what version it emits / expects)
- Create: `docs/runbooks/bridge-acceptance.md`
- Optional: `tests/fixtures/bridges/capcut-<version>/` golden snippets

**Interfaces:**
- Produces: (a) CapCut fixture(s) that pin a stated version; (b) a written acceptance runbook for Adobe (Premiere/AE) and Resolve that an operator follows on a machine that has the host.

- [ ] **Step 1** — Read `capcut.py` to find the emitted format/version; add fixture strings for that version so `generate_script` output can be compared against a golden prefix deterministically.
- [ ] **Step 2** — Write `docs/runbooks/bridge-acceptance.md`: for each bridge, the exact steps to (1) `omniframe bridge <id>` / detect, (2) generate a script, (3) open in the host, (4) record version + pass/fail attribution, and (5) record the verification level attained. Mark clearly that launching the host is a human/operator step.
- [ ] **Step 3** — Tests: a CapCut golden fixture assert only if the format is stable; otherwise assert non-empty + extension. Document the version pinned. No test opens a host.

---

## Acceptance gate (Phase 3)

Run and record:

```powershell
python -m compileall -q src
python -m pytest -q
python -m ruff check src tests
python -c "from omniframe.bridges import list_bridges; print('BRIDGES', [b['id'] for b in list_bridges()])"
```

Gate passes only if:
- full pytest zero failures (all new bridge tests included; host-marked tests skipped, not failed);
- every bridge answers `detect().installed is False` honestly on this machine (recorded in phase report);
- no fixture claims `render_tested`/`production_candidate`;
- `Docs/runbooks/bridge-acceptance.md` exists and makes host testing a separate operator step;
- lint adds no phase-introduced errors;
- `docs/phase-reports/phase3-bridges.md` written.

When the gate passes, continue to Phase 4 (UI and agent experience).