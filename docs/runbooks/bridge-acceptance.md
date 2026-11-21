# Bridge Acceptance Runbook

Host-application acceptance testing for the OmniFrame host bridges: **Adobe
Premiere Pro**, **Adobe After Effects**, **DaVinci Resolve**, **CapCut**, and
**Krita**.

> ## ⚠️ Hard honesty boundary (read first)
>
> Launching, opening, importing into, or rendering inside **any** proprietary
> host application is a **HUMAN / OPERATOR step**. It is *never* performed by
> the OmniFrame test-suite or by an automated bridge call on this machine.
>
> **On this development machine (the one the Phase-3 plan was verified on),
> none of Premiere Pro, After Effects, DaVinci Resolve, CapCut, or Krita is
> installed** — `omniframe doctor` reports each as `available: false`, and
> every bridge answers `detect().installed is False`. Consequently **no
> host-acceptance test in this project has been executed here, and none should
> be claimed as such.** Anything at verification level `import_tested`,
> `render_tested`, or `production_candidate` in this runbook's log is a
> **future operator claim**, never a statement about what ran on this machine.
>
> This runbook exists to tell an operator on a machine that **does** have the
> host exactly what to do, and to record what level was honestly attained.

---

## 1. Overview

Each bridge adapts OmniFrame's universal project to one professional tool and
shares one contract (`src/omniframe/bridges/base.py::ToolBridge`):

| Method | Purpose |
|---|---|
| `detect()` | Probe the machine for the host; never raises. |
| `capabilities()` | List what the bridge can do and via which tier. |
| `generate_script(project, output_dir)` | Write a host script/document; works even when the host is absent. |
| `inspect(target)` | Read-only structural probe of a host project file/folder. |

CLI surface (`src/omniframe/cli/main.py`, `bridge` typer app):

```powershell
# List every bridge and whether its host is installed
omniframe bridge list [--json]

# Detect a single bridge
omniframe bridge detect <bridge_id>

# Inspect an existing host project read-only
omniframe bridge inspect <bridge_id> <target>

# Generate a host script/document from an OmniFrame project
omniframe bridge script <bridge_id> <project.json> [--out <dir>]

# Environment doctor (confirms host availability + versions)
omniframe doctor --json
```

`<bridge_id>` is one of: `premiere_pro | after_effects | davinci_resolve |
capcut | krita`.

When no host is installed, generation still works and the bridge reports an
honest `host not detected` warning. That is the correct, expected behaviour;
do not treat it as a failure.

---

## 2. General acceptance procedure

For each bridge in scope, an operator on a host-equipped machine performs five
steps. Record the outcome of every step in the log table in §8.

1. **Detect the host** — confirm OmniFrame sees the installed application.
2. **Generate the artifact** — create the script/document from a project.
3. **Open / run the artifact in the host** — the operator step.
4. **Record host version + pass/fail attribution per capability.**
5. **Record the verification level attained** (see §7).

You need a valid OmniFrame project on disk. Create one with:

```powershell
omniframe project init my_demo --dir out
# or point at any existing .json project
```

Then generate each artifact (examples below). Each write is JSON-out so it can
be consumed by scripts. The `verify`/`render` semantics are read from
`GeneratedScript.summary`, `.metadata.sidecars`, and `.warnings`.

---

## 3. Adobe Premiere Pro (`premiere_pro`)

Artifacts produced by `generate_script`:
- `.jsx` ExtendScript (the primary artifact) — `GeneratedScript.path`
- `.fcpxml` sidecar (native Premiere interchange) — `metadata["sidecars"]`

### 3.1 Detect
```powershell
omniframe bridge detect premiere_pro
```
Expected when installed: `"installed": true`, `"version": "<e.g. 24.0>"`,
`scripting_api: true`.

### 3.2 Generate
```powershell
omniframe bridge script premiere_pro out/my_demo/project.json --out out/bridges/premiere
```
Records the `.jsx` path in `path` and the `.fcpxml` path in `metadata.fcpxml_path`.

### 3.3 Open/run in Premiere Pro — **operator step**
1. Launch **Adobe Premiere Pro** on the host machine (human action).
2. `File > Open Project…` and open the generated `.fcpxml` **OR** open a new
   project and run the script via `File > Scripts > Run Script File…`, selecting
   the generated `.jsx`.
3. Confirm the sequence named after the project builds, clips land at their
   timeline frames, tracks are created, and media imports resolve.
4. If `EXPORT_ENABLED` is on, confirm the render/export completes.

This step was **NOT executed on this machine** (host absent).

### 3.4 Record
Record the host version (edit > project settings / About), the `.jsx`/`.fcpxml`
paths, opened? (yes/no), and per capability (sequence_creation, media_import,
track_placement, cut_trim, transitions, audio_tracks, markers, render_export)
pass/fail.

---

## 4. Adobe After Effects (`after_effects`)

Artifacts:
- `.jsx` ExtendScript (primary) — `GeneratedScript.path`
- `*_ae_manifest.json` sidecar — `metadata["manifest_path"]`

### 4.1 Detect
```powershell
omniframe bridge detect after_effects
```

### 4.2 Generate
```powershell
omniframe bridge script after_effects out/my_demo/project.json --out out/bridges/ae
```

### 4.3 Open/run in After Effects — **operator step**
1. Launch **Adobe After Effects** (human action).
2. `File > Scripts > Run Script File…`, select the generated `.jsx`.
3. Confirm a composition matching the project's fps/size/duration is created,
   layers are added, keyframes/expressions apply, and the render queue gets an
   entry with the output path.

**NOT executed on this machine** (host absent).

### 4.4 Record
Host version, `.jsx`/manifest paths, opened? (yes/no), per capability
(composition_setup, layer_creation, keyframes, expressions, motion_vfx_presets,
render_queue) pass/fail.

---

## 5. DaVinci Resolve (`davinci_resolve`)

Artifacts:
- `.py` Python script driving the documented Resolve API — `GeneratedScript.path`
- `.xml` Resolve XML sidecar — `metadata["xml_path"]`

### 5.1 Detect
```powershell
omniframe bridge detect davinci_resolve
```
Note: Resolve's external scripting API requires the **Studio** edition. The
free edition exposes no scripting surface — record this in the notes.

### 5.2 Generate
```powershell
omniframe bridge script davinci_resolve out/my_demo/project.json --out out/bridges/resolve
```

### 5.3 Open/run in Resolve — **operator step**
1. Launch **DaVinci Resolve Studio** (human action).
2. Workspace > Scripts, paste/run the generated `.py` (or route the XML sidecar
   via File > Import > Timeline from the same folder when scripting is off).
3. Confirm project/timeline creation, media pool import, clip placement, and any
   Fusion/color/render hooks.

**NOT executed on this machine** (host absent).

### 5.4 Record
Host version + edition, `.py`/`.xml` paths, opened? (yes/no), per capability
(project_management, timeline_management, media_pool_import, clip_editing,
fusion_node_hooks, color_node_hooks, render_jobs) pass/fail.

---

## 6. CapCut (`capcut`) and Krita (`krita`)

### 6.1 CapCut

Artifacts — a draft *directory* rather than a single file:
- `<slug>_capcut_draft/draft_content.json` — `GeneratedScript.path`
- `<slug>_capcut_draft/manifest.json` — sidecar
- `<slug>_capcut_draft/materials/` — media staging folder

```powershell
omniframe bridge detect capcut
omniframe bridge script capcut out/my_demo/project.json --out out/bridges/capcut
```

**Operator step:** open CapCut, add a project and choose the generated draft
directory (`<stem>_capcut_draft`), copy referenced media into `materials/`, then
export manually (CapCut exposes no scriptable export API — this is an
`ui_automation` capability, `requires_host: true`).

The draft format is **version 13.0.0** and is pinned by a golden fixture (see
`tests/fixtures/bridges/capcut-13.0.0/` and
`tests/test_bridges_capcut_fixture.py`). Confirm the draft loads in your CapCut
build; the format is undocumented and version-specific.

**NOT launched on this machine** (host absent).

### 6.2 Krita

Artifacts:
- `krita_bridge.py` plugin — `GeneratedScript.path`
- `<slug>_krita_document/frames/` standalone frame folder — `metadata["document_dir"]`

```powershell
omniframe bridge detect krita
omniframe bridge script krita out/my_demo/project.json --out out/bridges/krita
```

**Operator step:** in Krita, Settings > Manage Python Plugins > Install from
File… select `krita_bridge.py`, enable it, then run from the Python Scripting
docker. Frame-sequence import/export also works standalone (no GUI).

**NOT launched on this machine** (host absent).

---

## 7. Verification levels

Taken from the Phase-1 contract (see
`src/omniframe/engines/code_video/renderer.py` and
`tests/test_bridges_verification.py`). Every bridge test and every operator
claim must state exactly one:

| Level | Meaning | Reachable without a host? |
|---|---|---|
| `generated` | Artifact produced and written to disk. | ✅ |
| `structurally_checked` | Artifact parses / structure-checks (e.g. valid JSON/XML, expected keys/tracks). | ✅ |
| `import_tested` | Artifact imported into the real host and reported loaded. | ❌ requires host |
| `render_tested` | Imported **and** rendered inside the real host. | ❌ requires host |
| `production_candidate` | Imported, rendered, and verified fit-to-produce. | ❌ requires host |

> **Rule:** on a machine with no host, a bridge can honestly claim at most
> `structurally_checked`. Marking a fixture `import_tested`/`render_tested`/
> `production_candidate` when the host was never opened is a hard
> honesty violation.
>
> On **this machine** every bridge fixture is `structurally_checked` **only**
> (see `tests/test_bridges_verification.py::BRIDGE_LEVELS`).

---

## 8. Operator log template

Copy this table (or keep it as a spreadsheets/markdown append) and fill a row
per bridge per acceptance run. A run is only credible if the operator records
the host version and whether the host was actually opened.

| Bridge | Host version | Command used | Artifact path | Opened? (yes/no) | Level attained | Pass/fail | Date | Operator |
|---|---|---|---|---|---|---|---|---|
| `premiere_pro` | | `omniframe bridge detect premiere_pro` / `…script …` | | | | | | |
| `after_effects` | | | | | | | | |
| `davinci_resolve` | | | | | | | | |
| `capcut` | | | | | | | | |
| `krita` | | | | | | | | |

**Pass criteria** for a single bridge: detection reported the host installed,
the artifact generated without unexpected errors, the operator opened/ran the
artifact in the host and recorded a pass/fail attribution per capability, and
the recorded verification level matches what the operator actually observed
(never higher than the strongest observed step).

---

## 9. Status on THIS machine (recorded during Phase 3)

`omniframe doctor --json` on the development machine:

```
premiere_pro    available: false   "Premiere Pro executable not located"
after_effects   available: false   "AfterFX.exe not located"
davinci_resolve available: false   "Resolve executable not located"
capcut          available: false   "CapCut executable not located"
krita           available: false   "krita executable not located"
```

Therefore: **no host was opened, no host-acceptance test was executed, and no
import/render/production claim is made.** Generated artifacts and their
`structurally_checked` fixtures are the only evidence produced here. This
runbook documents the operator procedure and records the honesty boundary; it
is evidence of *how to test*, not *of having tested* against a host.