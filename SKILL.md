---
name: omniframe-studio
description: Create, edit, render and verify videos and animations with OmniFrame Studio (the `omniframe` CLI, Python API, or MCP server). Use this skill whenever the user wants a video, motion graphic, kinetic title, code-explainer video, 2D cartoon animation, captions/audio-backed clip, timeline translation, or an export to Premiere Pro, After Effects, DaVinci Resolve, CapCut or Krita, even if they never say "OmniFrame". Also use it to install, update, diagnose or run the OmniFrame UI. Do not use it for still images or for editing video by hand inside a host app's GUI.
---

# OmniFrame Studio

OmniFrame turns a `project.json` timeline into deterministic PNG frames, then into a video.
You work by running typed commands/actions and reading their JSON results. You never guess.

## Rules that are never skipped

1. **Read before you change.** Open the project file and run `omniframe inspect timeline <project.json> --json` before editing. Run `omniframe tools --list` before using an action you have not used in this session.
2. **Never invent commands, flags, field names or error codes.** The only valid commands are in the table below. If unsure, run `omniframe <command> --help` or read `src/omniframe/agent/schemas/tools.json`. If still unclear, say so and ask.
3. **Checkpoint before editing an existing project:** `omniframe checkpoint save <project.json> --label before-<what>`. To undo: `omniframe checkpoint list`, then `omniframe checkpoint restore <id> <project.json>`.
4. **Evidence, not belief.** "Done" is allowed only after the Finish Gate passes. Show proof (paths, what you saw), not a claim.
5. **One change, then re-verify.** Do not stack several edits before validating again.
6. **Branch on `code`, not on message text.** Failed `run-tool` calls print JSON with a `code` field. Most commands exit non-zero on failure.
7. **Safety:** no `shell=True`, no exposed secrets, no DRM bypass, no patching proprietary binaries. Bridges use documented APIs or read-only inspection.

## Verified command reference

| Goal | Command |
|---|---|
| Check machine | `omniframe doctor --json` (exit 1 = not ready; `--fix` tries to install Chromium) |
| List actions | `omniframe tools --list` |
| Run any action | `omniframe run-tool <action> --params '<json>'` |
| New project | `omniframe project init <name> --dir <dir> --fps 30 --width 1920 --height 1080` |
| Validate | `omniframe project validate <project.json> --json` (exit 1 if errors; also checks assets) |
| Summary | `omniframe project report <project.json>` or `omniframe inspect timeline <project.json> --json` |
| Render frames | `omniframe project render <project.json> --out <dir> [--engine auto\|code_video\|cartoon_2d] [--backend auto\|playwright\|stub] [--resume]` |
| Compose video | `omniframe project compose <project.json> --frames <dir-of-PNGs> --out <video.mp4> [--preset h264]` |
| Look at video | `omniframe inspect media --video <video.mp4> --output-dir <dir> --count 8 --contact-sheet <sheet.png>` |
| Look at frames | `omniframe inspect frames --directory <dir> --output <sheet.png> --columns 4` |
| Translate format | `omniframe project translate --translator <name> <project.json> --out <output>` |
| Pick engine | `omniframe route --capability <name>` |
| Bridges | `omniframe bridge list`, `bridge detect <name>`, `bridge script <name> <project.json> --out <dir>`, `bridge inspect <name> <target>` |
| Start UI / MCP | `omniframe ui --host 127.0.0.1 --port 8765` / `omniframe mcp` |

Bridge names: `premiere_pro`, `after_effects`, `davinci_resolve`, `capcut`, `krita`.
Translator names: `fcpxml`, `edl`, `capcut_draft`, `ae_manifest`, `resolve_xml`.

## The loop (in order, no skipping)

**Step 1. Understand.** Restate the goal in one sentence: output type, duration, resolution, audio/captions, target host (if any). If a missing detail would change the result, ask one short question; otherwise state your assumption and continue.

**Step 2. Check the environment.** `omniframe doctor --json`.
- FFmpeg missing: compose and inspect will fail. Stop and report the repair step.
- Chromium/Playwright missing: code-scene rendering fails (or degrades to the stub backend). Try `omniframe doctor --fix`, else report.
- `native_accelerator = python-fallback` is normal.

**Step 3. Plan in writing (3 to 7 lines).** Which example or template you start from, which scenes, which commands, how you will check the result. For non-trivial work, name two approaches in one line each and say why you chose one.

**Step 4. Build or edit.** Start from the closest folder in `examples/` (`code-explainer`, `cartoon-bounce`, `full-studio-demo`, `handwashing-2d`, `omniframe-promo`) or `project init`, not a blank file. Then run `project validate --json`. Fix every error before moving on.

**Step 5. Preview first, full render second.** Copy the project JSON; set `meta.width` / `meta.height` to half, and `meta.duration_frames` to a few seconds. If a clip still runs past the new end, clamp its `start_frame` + `duration_frames`. Render and compose that copy first. Only then render the real project.

**Step 6. Look at it.** Run `inspect media` on the composed video, then actually open the contact sheet and several extracted frames as images. Judge them against the Finish Gate.

**Step 7. Fix or finish.** If anything fails, change one thing and go back to Step 4. After 3 failed attempts on the same problem, stop and report: what you tried, the error `code`s, your best guess at the cause.

## Finish Gate (all must be true before you say "done")

- [ ] `project validate` passed with no errors.
- [ ] The video exists and has the expected duration and resolution.
- [ ] The contact sheet shows no blank, black or frozen frames.
- [ ] Text is fully visible: not cut off, not overlapping, readable.
- [ ] Motion changes across frames as intended (not static, not jumping).
- [ ] If audio/captions were requested, they are present in the output.
- [ ] If a bridge was used: you read its loss report and told the user what is lost, and which host files are only *generated* vs actually *tested* in the host app.

Final message: output path, what you checked, and anything you could NOT verify.

## Thinking protocol for hard or unclear tasks

Use when there are 3+ scenes, mixed engines, a host-app target, or something has failed twice.

1. **Break down** into the smallest pieces (scene, text, motion, audio, export).
2. **Find the riskiest piece** and test it alone first.
3. **Compare two options**, one line each, pick one, say why.
4. **Predict** the output before running a command. If reality differs, stop and explain why before continuing. A surprise is information.
5. **Change one thing**, re-check.

## Error codes (branch on `code`)

| Code | Meaning | What to do |
|---|---|---|
| `E_SCHEMA` | JSON does not match the project schema | Fix the field at the reported path only; compare with an example project |
| `E_VALIDATION` | Timeline is well-formed but inconsistent (overlaps, bad references, missing assets) | Fix exactly what each issue says; re-run `validate --json` |
| `E_ENGINE_UNAVAILABLE` | Engine/backend not installed or unusable | Run `doctor`, install the missing piece or pick another `--engine/--backend` |
| `E_DEPENDENCY_MISSING` | An optional Python package is needed | Install the extra (`.[render]`, `.[ui]`, `.[native]`) |
| `E_RENDER` | Frame rendering failed | Re-run on one short clip; read `details` (scene + console log); check `__OMNIFRAME_READY__` for async content |
| `E_RENDER_CANCELED` | Render was canceled or timed out | Retry with a shorter clip or `--resume` |
| `E_PATH_SECURITY` | A path escaped the allowed workspace | Use paths inside the project workspace; never bypass |
| `E_PRECONDITION` | Missing asset, host or prerequisite | Provide the missing item; do not retry unchanged |
| `E_CHECKPOINT` | Checkpoint save/restore failed | `checkpoint list`, check the id and project path |
| `E_BRIDGE_UNAVAILABLE` | Host app not installed or reachable | Not a bug. Tell the user; use `bridge script` output or a file-based path |
| `E_BRIDGE` | Host rejected the operation or script | Read details; fall back to the generated script for manual import |
| `E_TOOL_NOT_FOUND` | Action name unknown | `omniframe tools --list` and use an exact name |
| `E_ACTION` | An action raised while running | Read `details`; fix input, do not retry unchanged |
| `E_MIGRATION` | Database/schema migration problem | Stop. Never delete the database; report to the user |

For any other code: read the full JSON error; never repeat the same call unchanged.

## Gotchas

- Rendering is deterministic (seeded per-frame PRNG, frozen CSS animations, exact frame numbers). Do not use `Math.random()` or wall-clock time in scene HTML. If content loads async, signal `__OMNIFRAME_READY__`.
- `--stream-to-ffmpeg` needs exactly one renderable clip (`code_scene` or `cartoon_layer`), writes no PNG checkpoints, and cannot be combined with `--resume`.
- The default PNG render is resumable. Prefer it for long jobs.
- `compose` needs the PNG folder of the specific clip (e.g. `out/<name>/<clip-id>`), not the whole output folder.
- `project validate` always checks assets, so a missing file shows up as a validation issue.
- Update checks work offline from cache; a GitHub outage is not a task failure.

## Worked example

Goal: "Make a short code-explainer intro."

1. Plan: copy `examples/code-explainer/project.json`, change title text, preview, then full render.
2. `omniframe doctor --json` shows ready.
3. `omniframe checkpoint save projects/intro/project.json --label before-edit`
4. Edit text, then `omniframe project validate projects/intro/project.json --json` returns ok.
5. Preview copy: render, compose, then `omniframe inspect media --video out/intro-preview.mp4 --output-dir out/inspect --count 8 --contact-sheet out/inspect/sheet.png`. Open the sheet: the title is clipped in frame 6.
6. Shorten the title, validate, render again. Sheet is clean.
7. Full render and compose, inspect once more.
8. Report: `out/intro.mp4`, what was checked (8 frames, title fits), not verified: audio (none requested).

## More detail (read only when needed)

- Install, update, UI, MCP setup: `references/install-update.md`
- Action contracts: `src/omniframe/agent/schemas/tools.json`
- Programming guide: `src/omniframe/agent/AGENT_GUIDE.md`
- Repository: <https://github.com/amitkumardas3624/omniframe-studio>
