# “পরিষ্কার হাত, সুস্থ জীবন” — 2D Educational Video Design

**Date:** 2026-11-21
**Status:** Creative design approved; implementation pending written-spec review

## Purpose

Create an original 10-second Bengali educational animation using OmniFrame Studio’s Cartoon2D/Pillow pipeline. The lesson is simple: wash hands with water and soap for 20 seconds before eating.

## Rights and style boundary

The characters, motion, copy, colors, sound, and timing are original. They must not reproduce a real person’s face, voice, likeness, or exact signature style. The visual direction is a generic Bangladeshi classroom/home educational animation with warm colors and expressive human-like 2D characters.

## Format

- Duration: 10 seconds
- Canvas: 1920×1080
- Frame rate: 30fps
- Total frames: 300
- Language: Bengali captions and educational copy
- Delivery: H.264 MP4 with original procedural audio bed; captions also delivered as SRT

## Storyboard

| Time | Scene | Visual | Copy |
|---|---|---|---|
| 0–2s | Problem | A generic Bangladeshi schoolchild reaches for a snack; small original germ icons appear near the hands. | `খাওয়ার আগে?` |
| 2–5s | Three steps | A friendly teacher reveals three cards in sequence: water, soap, and a 20-second timer. | `১ পানি` · `২ সাবান` · `৩ ২০ সেকেন্ড` |
| 5–8s | Action | The child washes hands at a tap; soap bubbles and a circular timer animate around the hands. | `ভালোভাবে হাত ধুয়ে নিন` |
| 8–10s | Reminder | Teacher and child smile; a clean sparkle resolves into the final title card. | `পরিষ্কার হাত, সুস্থ জীবন` / `খাওয়ার আগে হাত ধুয়ে নিন` |

## Characters and assets

- Child: original vector/painterly human-like 2D character with generic clothing and features.
- Teacher: original friendly human-like 2D character with generic clothing and features.
- Germ icons: original abstract circles/spikes, not based on a known mascot.
- Props: original faucet, soap, timer, snack plate, and classroom/home background.
- Audio: original procedural light rhythm and water/sparkle sound accents; no downloaded music or reference audio.
- External downloads are not required. If any external asset is added, record its URL, author, license, and checksum before rendering.

## Pipeline

1. Build a 300-frame OmniProject using `cartoon_layer` clips and original vector/solid/text layers.
2. Render with the existing Python Cartoon2D/Pillow fallback so Chromium is not required.
3. Generate Bengali captions as `captions.srt`.
4. Generate a deterministic original audio bed with stdlib `wave` and mux it through the existing FFmpeg Compositor.
5. Generate a contact sheet and `inspection.json` with resolution, frame rate, duration, and audio/video stream checks.

## Acceptance criteria

- Project validates with `omniframe project validate`.
- Output is 1920×1080, 30fps, 300 frames, approximately 10 seconds.
- Final MP4 includes H.264 video and AAC stereo audio.
- Bengali captions are readable and match the four storyboard timings.
- Child, teacher, props, and germ icons are original and visually distinct.
- No real-person likeness, copied style signature, reference frame, copyrighted song, or unlicensed asset is present.
- Focused animation tests and the complete repository test suite pass.
- Generated media stays in an ignored output directory; no new source commit is required for this QA/demo render.
