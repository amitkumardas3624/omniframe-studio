# OmniFrame Studio Agent Guide

For the complete API and action-by-action guide, see `src/omniframe/agent/AGENT_GUIDE.md`.

## Quick reference

```powershell
omniframe doctor
omniframe tools --list
omniframe project validate examples/code-explainer/project.json
omniframe project render examples/code-explainer/project.json --out out/render
omniframe project compose examples/code-explainer/project.json --frames out/render/intro --out out/video.mp4
omniframe inspect media --video out/video.mp4 --output-dir out/inspect --contact-sheet out/inspect/sheet.png
omniframe mcp
```

Before mutating project state, use `omniframe checkpoint save <project.json> --label before-edit`. Use structured JSON output and stable error codes for agent branching. For the current action registry, run `omniframe tools --list` or inspect `src/omniframe/agent/schemas/tools.json`.
