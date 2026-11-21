CapCut draft format version PINNED: 13.0.0

Source of truth: src/omniframe/core/timeline_schema/translate.py
`CapCutDraftTranslator.from_universal()` emits a literal `"version": "13.0.0"`
top-level key (see translate.py near the end of `from_universal`), which the
CapCut bridge serialises verbatim into `draft_content.json`.

Pin decision (Task 4):
- STABLE: the version marker is a hard-coded literal in the emitted format, so
  it is deterministic and can be pinned now.
- The golden fixture in this directory (`draft_content.json`) is the exact,
  fully-qualified output the bridge must produce for the canonical pin project
  (a 30 fps 1920x1080 "capcut-pin" project with one audio and one video track
  and no declared Asset records, hence empty `materials`).
- The asserting test deep-equals the generated draft against this golden file.
  If a future refactor legitimately changes the emitted draft structure, this
  test fails loudly — at that point the version pin must be re-verified and the
  golden regenerated, never silently overwritten.

Rules:
- Never edit this golden by hand to "make the test pass"; regenerate it only
  when the emitted CapCut draft format has intentionally changed and the
  version marker has been re-confirmed.
- This fixture pin is generation-only; it never opens a CapCut host.