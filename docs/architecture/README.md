# Architecture notes - OmniFrame Studio

Two documents, written for whoever picks this repository up next, human or a
different agent:

| file | what it is for |
|---|---|
| `system-map.md` | what the system is made of: layers, data model, render pipeline, the verification ladder, the HTTP and UI surfaces, the 7A compare gate, conventions, and the commands that prove each layer is alive. |
| `handover-2026-11-27-editor-phase5.md` | the state of the Studio editor at 2026-11-27: what changed in the compare-gate phase, why each decision was made, what was actually verified and how, what is still unverified, and the questions I would want a reviewer to answer before extending it. |

Existing documents these sit beside:

| path | contents |
|---|---|
| `docs/superpowers/specs/2026-11-25-studio-editor-live-preview-design.md` | the Studio editor design spec; its phases 1-5 are the ones implemented here |
| `docs/superpowers/specs/` | design specs: the platform-hardening work, the promo, the 2D sample, the native accelerator |
| `docs/superpowers/plans/` | the platform-hardening implementation plans (roadmap binaries and phases 0-5) |
| `docs/phase-reports/` | reports for the platform-hardening roadmap phases, `phase0-correctness.md` through `phase5-release.md` |
| `docs/compare-gate.md` | the executed section 7A compare gate record for the motion-reel template |
| `docs/runbooks/bridge-acceptance.md` | manual acceptance procedure for host bridges |
| `AGENT_GUIDE.md`, `src/omniframe/agent/*` | the agent-facing guide, skill and generated tool manifest |

## One naming hazard, so nobody misreads the history

Two unrelated things are called "Phase 5" in this repository.

- `docs/phase-reports/phase5-release.md` is the release phase of the **platform
  hardening roadmap** (phases 0-5: correctness, rendering, jobs and safety,
  bridges, UI, release).
- The **Studio editor spec** has its own phases 1-5: editor shell, scrub preview,
  timeline editing, inspector, and the compare gate.

Commits in this folder refer to the editor spec. When a message says "Phase 5"
without a noun, the recent ones mean the compare gate.
