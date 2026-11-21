# OmniFrame Compatibility Matrix

This matrix is generated from evidence, not from intent. The rule is the same one
encoded in `src/omniframe/release/compat.py`:

> A codec is `render_tested` only when an artifact was produced on this machine
> **and** read back with `ffprobe`. A codec merely appearing in `ffmpeg -encoders`
> is reported as `capability`, and capability never promotes `status`.

Reproduce the table below with:

```bash
python -c "from omniframe.release.compat import compatibility_report; import json; print(json.dumps(compatibility_report({'os': 'Windows 11', 'python': '3.12.10', 'ffmpeg': '8.1.1-full_build-www.gyan.dev'}), indent=2))"
```

## Machine and environment

| Fact | Value |
| --- | --- |
| OS | Windows 11 (`platform.release()` 11, `11.0.26300` build kernel) |
| Architecture | AMD64 (x64) |
| Python | CPython 3.12.10 |
| FFmpeg | ffmpeg 8.1.1-full_build-www.gyan.dev (`libx264`, `libx265`, `libvpx`, `prores`, `qtrle`, `gif` present) |
| FFprobe | 8.1.1-full_build-www.gyan.dev |
| Node | v24.14.0 |
| Chromium (Playwright) | 151.0.7922.34 |
| Native accelerator | **absent** — `omniframe._native._omniframe_native` is not built here |

Probe method: a 16×16, 3-frame synthetic (`rawvideo`/`rgb24`, alternating black and
white) clip is encoded with each probed preset's own codec and `extra_args`, then
`ffprobe` must report a `codec_type: video` stream in the produced file. A pass
records `render_tested`; anything else stays `unverified`.

## Tested here

| Preset | Container | Video codec | Audio codec | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `h264` | mp4 | libx264 | aac | `render_tested` | encoded 1623 bytes; `ffprobe` read `codec_name='h264'` |
| `webm` | webm | libvpx-vp9 | libopus | `render_tested` | encoded 617 bytes; `ffprobe` read `codec_name='vp9'` |
| `gif` | gif | gif | none | `render_tested` | encoded 957 bytes; `ffprobe` read `codec_name='gif'` |

`h264` is the platform's default delivery preset and is the only export path
exercised by the Phase 1 golden-frame gate; the probe above re-confirms the encoder
itself on this machine at the time of the release run. Sizes differ per codec
because the codec differs, not because the input does.

## Not tested here

| Preset | Container | Video codec | Audio codec | Status | Why |
| --- | --- | --- | --- | --- | --- |
| `h265` | mp4 | hevc | aac | `unverified` | no artifact produced here. Capability reports `encoder_missing` because ffmpeg's encoder is named `libx265`, not `hevc`; the preset's codec name is the ffmpeg *encoder selection*, so a raw name match cannot vouch for it |
| `prores` | mov | prores_ks | pcm_s16le | `unverified` | no ProRes master was produced or read back on this machine |
| `qtrle_alpha` | mov | qtrle | none | `unverified` | no alpha-bearing QuickTime RLE artifact was produced; alpha correctness can only be claimed from a real file with a transparent region |
| `png_sequence` | image2 | png | none | `unverified` | frame sequences are written by the compositor's own writer path, not by the single-file probe |

`import_tested` is currently assigned to nothing by default, on purpose: this module
will not claim that a file was imported just because the platform has a decoder for
it. Supplying `evidence={"prores": "render_tested"}` to `compatibility_report` after
a real export is the documented way to raise a status, and the reason string records
that it came from the caller.

## Host applications

No proprietary DCC host was present on this machine, so nothing below is testable
here and nothing is claimed:

| Host | Bridge | Status |
| --- | --- | --- |
| Adobe Premiere Pro | `bridges/premiere_pro.py` | host not installed — runbook only (`docs/runbooks/bridge-acceptance.md`) |
| Adobe After Effects | `bridges/after_effects.py` | host not installed — runbook only |
| DaVinci Resolve | `bridges/davinci_resolve.py` | host not installed — runbook only |
| CapCut | `bridges/capcut.py` | host not installed; CapCut 13.0.0 script shape is pinned by a fixture, **not** by a verified import |
| Krita | `bridges/krita.py` | host not installed — runbook only |

`omniframe doctor --json` reports each of these as `available: false`. The
`bridge_host` pytest marker selects the tests that require a real, installed host;
they are skipped on this machine and that skip is the honest result. CapCut's
`tests/fixtures/bridges/capcut.py-13.0.0/` fixture is a **structure** check of the
script we would hand to the host — it is `structurally_checked`, never
`import_tested`.

## Release 0.2.0 verification

The report was re-executed at release time on the machine described above, with the release commit
built and installed, and returned the identical result:

```
summary = {"unverified": 4, "import_tested": 0, "render_tested": 3}
```

`h264`, `webm`/VP9 and `gif` remain `render_tested` because they were encoded and probed again
during the release run; `h265`, `prores`, `qtrle_alpha` and `png_sequence` remain `unverified`
because no artifact for them was produced. The wheel was additionally installed into a clean
virtual environment and imported cleanly (`omniframe 0.2.0`), but that proves packaging, not codec
or host behaviour — it changes no row in either table above.

## What this means for a release

- Deliveries targeting `h264`, `webm`/VP9 and GIF are backed by a produced artifact
  on this machine.
- Deliveries targeting ProRes, QuickTime RLE with an alpha channel, HEVC, or PNG
  sequences are shipping code that has not been proven to emit a valid file here;
  they must be verified on a machine that actually produces them before being
  announced as supported.
- No DCC bridge is `production_candidate` on this machine. The runbook in
  `docs/runbooks/bridge-acceptance.md` is the operator procedure that turns each
  row above into a real claim.
