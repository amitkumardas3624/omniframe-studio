# OmniFrame Studio — পূর্ণ Technical Audit

**অডিটের ধরন:** repository, implementation, runtime, bridge, translator, UI এবং open-source alternative audit  
**ভাষা:** বাংলা  
**টার্গেট audience:** developer, maintainer, technical reviewer এবং AI-agent platform architect  
**অডিট scope:** local checkout এবং ব্যবহারকারীর দেওয়া public GitHub repository  
**অডিটের সীমা:** এই নথিতে source code পরিবর্তন করা হয়নি; proprietary host-এর end-to-end import/export বাস্তবে চালিয়ে দেখা হয়নি।

---

## 1. Executive verdict

OmniFrame Studio একটি **কার্যকর alpha-stage, agent-first media orchestration ও rendering foundation**। এটি এখনই একটি পূর্ণাঙ্গ Premiere Pro, After Effects বা CapCut clone নয়। এর প্রকৃত শক্তি হলো:

- AI agent-এর জন্য typed action registry এবং JSON-schema contract;
- universal timeline/project model;
- HTML/CSS/JS scene rendering;
- Pillow-ভিত্তিক 2D frame pipeline;
- FFmpeg-ভিত্তিক composition/export;
- checkpoint, validation, inspection এবং translation;
- Premiere Pro, After Effects, DaVinci Resolve, CapCut ও Krita-এর দিকে bridge/sidecar generation।

**সামগ্রিক maturity verdict: `Alpha / foundation-ready, production-ready নয়`.**

| মূল্যায়ন | verdict |
|---|---|
| Agent orchestration/control plane | **বিদ্যমান এবং promising** |
| Deterministic code-video rendering | **বিদ্যমান; Playwright ছাড়া degraded fallback** |
| Pillow-based 2D animation | **বিদ্যমান; native accelerator optional/unavailable** |
| FFmpeg composition | **বিদ্যমান; focused coverage আছে** |
| Universal timeline ও translation | **বিদ্যমান; lossless round-trip প্রমাণিত নয়** |
| DCC bridge | **আংশিক/experimental** |
| Full NLE editor | **অনুপস্থিত** |
| Full After Effects-style compositing/VFX | **অনুপস্থিত** |
| Production-grade host interoperability | **প্রমাণিত নয়** |
| Production release readiness | **না** |

### এক বাক্যের সিদ্ধান্ত

OmniFrame-কে **“AI-agent-এর media control plane এবং interchange/bridge layer”** হিসেবে এগিয়ে নেওয়া বাস্তবসম্মত; “সব proprietary creative application-এর open-source replacement” হিসেবে দাবি করা বর্তমান implementation দিয়ে সমর্থনযোগ্য নয়।

---

## 2. Repository identity এবং audit boundary

### 2.1 ব্যবহারকারীর দেওয়া public repository

পর্যালোচিত public repository:

- URL: <https://github.com/amitkumardas3624/omniframe-studio>
- দৃশ্যমান branch: `master`
- দৃশ্যমান latest commit: `4759e40`
- commits: 14
- stars: 0
- forks: 0
- published releases: নেই
- license: MIT

### 2.2 Local checkout

এই audit-এর local checkout-এর metadata:

- latest local commit: `6749271 fix: report deterministic promo render backend accurately`
- configured remote: <https://github.com/gbd718106-cmyk/omniframe-studio.git>
- working tree-তে untracked handwashing example/test এবং generated output আছে।

### 2.3 গুরুত্বপূর্ণ source-of-truth ঝুঁকি

Public repository, local remote এবং `pyproject.toml`-এর metadata একই উৎস নির্দেশ করছে না:

- README installer `gbd718106-cmyk/omniframe-studio` ব্যবহার করে;
- `pyproject.toml`-এর Homepage/Documentation/Issues `omniframe-studio/omniframe-studio` নির্দেশ করে;
- ব্যবহারকারীর দেওয়া repository হলো `amitkumardas3624/omniframe-studio`;
- local checkout-এর latest commit public repository-র দৃশ্যমান latest commit-এর সঙ্গে মেলে না।

**ফল:** এই audit local implementation এবং user-provided public repository—দুইটিকে আলাদা evidence হিসেবে দেখে। Release বা production claim করার আগে repository identity একীভূত করতে হবে।

> **সমাধান (২০২৬-১১-২২):** ব্যবহারকারী canonical URL হিসেবে
> `https://github.com/amitkumardas3624/omniframe-studio` নির্দেশ করেছেন — কারণ GitHub
> username বদলে গেলেও পুরোনো slug ছিল। ফলে git remote `origin`, `install.sh`, `install.ps1`,
> `README.md`, `SKILL.md`, `pyproject.toml`-এর `[project.urls]`, updater-এর default repo slug
> ও server-এর fallback link — সব একই canonical URL-এ আনীত হয়েছে, এবং
> `Documentation` URL `tree/main`-এর বদলে `tree/master` হয়েছে। পুরোনো URL আর কোথাও নেই;
> `tests/test_installers.py`-এ এর জন্য drift guard যোগ হয়েছে। বিস্তারিত:
> `docs/repository-identity.md`। উপরের পর্যবেক্ষণগুলো audit-এর সময়কার অবস্থা হিসেবে রাখা
> হয়েছে — মুছে ফেলা হয়নি।

---

## 3. ঘোষিত architecture বনাম বাস্তব architecture

README এবং `pyproject.toml` অনুযায়ী stack:

- Python `>=3.10`
- Pydantic
- PyYAML
- Typer
- Pillow
- FFmpeg/ffprobe
- optional Playwright/Chromium
- optional pybind11/native extension
- optional FastAPI/Uvicorn UI/API

মূল architecture:

```text
AI agent / MCP client / CLI / Web UI
                  |
          Action Registry
                  |
        Universal OmniProject timeline
          /          |          \
   code-video     cartoon-2d    compositor
  Playwright       Pillow         FFmpeg
          \          |          /
        validation / inspection / checkpoints
                  |
       translators এবং DCC bridges
```

প্রাসঙ্গিক source location:

- timeline model/validation/translation: `src/omniframe/core/timeline_schema/`
- action runtime/checkpoint/inspection: `src/omniframe/core/agent_runtime/`
- rendering engines: `src/omniframe/engines/`
- DCC adapters: `src/omniframe/bridges/`
- FastAPI/MCP/UI backend: `src/omniframe/backend/`
- agent schema/guide: `src/omniframe/agent/`

এই architecture একটি **control plane**-এর জন্য যুক্তিসঙ্গত। কিন্তু এটি host application-এর internal editor, effect engine, GPU compositor, media database বা proprietary project semantics প্রতিস্থাপন করে না।

---

## 4. Feature matrix

Status-এর অর্থ:

- **বিদ্যমান:** source-এ implementation আছে এবং অন্তত focused test/inspection evidence আছে।
- **আংশিক:** মূল interface আছে, কিন্তু host/dependency/format/coverage সীমাবদ্ধ।
- **অনুপস্থিত:** বর্তমান scope-এ implementation নেই বা clone-level capability নেই।
- **Production-complete নয়:** capability আছে, কিন্তু reliability, compatibility, security বা end-to-end proof অসম্পূর্ণ।

| Feature | Status | Evidence / মন্তব্য |
|---|---|---|
| Universal project/timeline model | বিদ্যমান | Pydantic model, tracks, clips, assets, render targets |
| JSON/YAML project loading | বিদ্যমান | timeline schema IO |
| Semantic project validation | বিদ্যমান | asset/path এবং schema validation |
| JSON Schema export | বিদ্যমান | agent/tool contract-এর ভিত্তি |
| Timeline report | বিদ্যমান | agent-readable project summary |
| Timeline diff | বিদ্যমান | `timeline.diff` action |
| Checkpoint save/list/restore/diff | বিদ্যমান | destructive edit-এর আগে rollback surface |
| HTML/CSS/JS frame rendering | বিদ্যমান | Playwright + Chromium backend |
| Browser scene error reporting | বিদ্যমান | backend issue/stack location reporting |
| Browser ছাড়া deterministic rendering | বিদ্যমান, degraded | `StubBackend` placeholder frame তৈরি করে; বাস্তব scene render নয় |
| Pillow 2D cartoon pipeline | বিদ্যমান | layers, keyframes, easing, frame render |
| Native C++/pybind11 accelerator | আংশিক | optional; বর্তমান doctor-এ unavailable |
| FFmpeg video composition | বিদ্যমান | frame-to-video, concat, audio mux, subtitle/LUT-related helpers |
| Audio mixing/ducking | আংশিক | interface ও focused tests আছে; broad production matrix প্রমাণিত নয় |
| Subtitle handling | আংশিক | metadata/burn-in workflow আছে; full subtitle editor নয় |
| H.264/HEVC/ProRes/WebM export presets | বিদ্যমান | compositor preset surface; all codec combinations end-to-end যাচাই হয়নি |
| Visual inspection/contact sheet | বিদ্যমান | frame/media inspection tools |
| CLI | বিদ্যমান | validate/render/compose/inspect/doctor/update surfaces |
| Native stdio MCP server | বিদ্যমান | action registry expose করে |
| FastAPI REST API | বিদ্যমান | actions, projects, bridges, environment, update endpoints |
| WebSocket activity stream | বিদ্যমান | `/ws/agent-activity` |
| Local Web UI | আংশিক | monitoring/tool launcher; full timeline editor নয় |
| Agent tool registry | বিদ্যমান | runtime-এ 19 registered action |
| Action schema documentation | drift আছে | `tools.json` ও guide এখনও 18 actions বলে |
| FCPXML translation | আংশিক | interchange mapping; Premiere/Resolve fidelity প্রমাণিত নয় |
| Resolve XML translation | আংশিক | sidecar generation; host import test হয়নি |
| EDL translation | আংশিক | basic CMX3600 interchange; effects/metadata loss স্বাভাবিক |
| CapCut draft translation | experimental | undocumented/version-specific JSON |
| AE manifest translation | আংশিক | OmniFrame bridge-এর own manifest; `.aep` নয় |
| Premiere Pro bridge | আংশিক | ExtendScript + FCPXML + read-only `.prproj` inspection |
| After Effects bridge | আংশিক | ExtendScript + manifest + read-only `.aep/.aepx` inspection |
| DaVinci Resolve bridge | আংশিক | documented API script + XML; Studio constraint |
| CapCut bridge | experimental | draft generation/inspection; export manual UI workflow |
| Krita bridge | আংশিক | frame/plugin/audio helpers; NLE replacement নয় |
| Full Premiere clone | অনুপস্থিত | native sequence/editor/effects ecosystem নেই |
| Full After Effects clone | অনুপস্থিত | layer/effect/expression/comp engine নেই |
| Full CapCut clone | অনুপস্থিত | editor, cloud/project ecosystem, export engine নেই |
| Full Motion Canvas clone | অনুপস্থিত | OmniFrame Motion Canvas runtime নয়; conceptually compatible code-video layer মাত্র |
| Multi-user auth/RBAC | অনুপস্থিত/প্রমাণিত নয় | API surface-এ production identity boundary দেখা যায়নি |
| Durable job queue/worker orchestration | অনুপস্থিত/আংশিক | process-local action execution; distributed worker proof নেই |
| Host-independent end-to-end bridge CI | অনুপস্থিত | proprietary hosts বর্তমান machine-এ installed নয় |
| Release/packaging discipline | আংশিক | `0.1.0`, Alpha; public release নেই |

---

## 5. Rendering এবং media pipeline audit

### 5.1 Code-video / browser rendering

`src/omniframe/engines/code_video/backends.py`-এ দুটি backend আছে:

1. **`PlaywrightBackend`** — headless Chromium ব্যবহার করে scene render করে।
2. **`StubBackend`** — dependency-free Pillow placeholder renderer।

Source-এ fallback-টি স্পষ্টভাবে deterministic placeholder হিসেবে চিহ্নিত। Chromium অনুপস্থিত হলে warning সহ fallback হয়। তাই:

- `StubBackend` pipeline test, CI এবং deterministic smoke output-এর জন্য উপযোগী;
- কিন্তু placeholder output-কে HTML/CSS/JS scene-এর production render বলা যাবে না;
- `doctor`-এ Chromium available থাকলেও প্রতিটি production scene, animation timing, font, browser security এবং visual regression end-to-end যাচাই করা হয়নি।

### 5.2 2D cartoon pipeline

Pillow engine-এ layer, position, rotation, scale, skew, anchor, keyframe এবং easing-এর মতো primitive আছে। এটি deterministic 2D frame-generation-এর জন্য ভালো ভিত্তি।

তবে এটি সম্পূর্ণ animation authoring application নয়। বর্তমান scope-এ নিম্নোক্ত বিষয়গুলো পূর্ণাঙ্গ editor-level capability হিসেবে প্রমাণিত নয়:

- vector drawing/editing workspace;
- onion skin এবং interactive rigging;
- reusable character rig/IK;
- shape layer/effect graph;
- audio-synced animation editor;
- GPU compositing;
- non-destructive visual authoring UI।

### 5.3 Native accelerator

Optional pybind11/native extension আছে, কিন্তু runtime doctor-এ native extension unavailable এবং Python fallback চলছে। এটি correctness blocker নয়, কিন্তু production-scale frame count, memory এবং render throughput-এর জন্য গুরুত্বপূর্ণ সীমাবদ্ধতা।

### 5.4 FFmpeg compositor

FFmpeg/ffprobe available এবং focused compositor tests পাস করেছে। Video/audio/subtitle/export workflow-এর building blocks আছে। তবে production readiness নির্ধারণে এখনও প্রয়োজন:

- codec/container compatibility matrix;
- long-duration render soak test;
- corrupt/missing asset recovery;
- cancellation/resume semantics;
- deterministic output hash বা golden media tests;
- Windows/Linux/macOS parity;
- GPU encoder matrix;
- large project memory profiling।

---

## 6. Timeline, validation এবং translation audit

Universal timeline ধারণাটি OmniFrame-এর সবচেয়ে গুরুত্বপূর্ণ architectural decision। একটি canonical `OmniProject` থেকে বিভিন্ন engine এবং host format-এ যাওয়ার ফলে agent orchestration সহজ হয়।

Registered translators:

- `fcpxml`
- `resolve_xml`
- `edl`
- `capcut_draft`
- `ae_manifest`

### 6.1 Translation-এর বাস্তব অর্থ

এই translators-কে **interchange adapters** হিসেবে দেখা উচিত, full-fidelity converters হিসেবে নয়। সাধারণত নিচের তথ্য loss বা approximation হতে পারে:

- proprietary effect parameters;
- plug-in identity এবং version;
- expression/automation graph;
- blend mode-এর exact semantics;
- color-management metadata;
- nested sequence/compound clip semantics;
- masks, mattes, adjustment layers;
- audio automation এবং plugin state;
- font availability ও rasterization differences;
- host-specific markers এবং metadata।

### 6.2 Format-specific conclusion

- **FCPXML/Resolve XML:** standard-ish interchange-এর কারণে সবচেয়ে বাস্তবসম্মত sidecar path; তবু import result host-এ খুলে যাচাই না করলে success বলা যাবে না।
- **EDL:** basic edit decision interchange-এর জন্য ভালো; modern effects, audio এবং compositing বহন করতে পারে না।
- **CapCut draft:** undocumented এবং version-specific; generated JSON load হবে—এটি target CapCut build-এ যাচাই আবশ্যক।
- **AE manifest:** bridge-specific intermediate manifest; এটি `.aep` binary project নয়।

---

## 7. Bridge audit

Bridge base class capability-কে তিন tier-এ ভাগ করেছে:

1. `documented_api` — host-এর প্রকাশিত scripting API;
2. `reverse_engineered` — format structure read/write, কিন্তু binary patch নয়;
3. `ui_automation` — শেষ বিকল্প, ভঙ্গুর এবং opt-in হওয়া উচিত।

এই classification নৈতিক ও engineering দিক থেকে সঠিক। এটি proprietary binary patch বা DRM bypass-এর দাবি করে না।

### 7.1 Premiere Pro

বর্তমান bridge:

- ExtendScript generate করে;
- FCPXML sidecar তৈরি করতে পারে;
- `.prproj` read-only structural inspection করে;
- host application installed না থাকলেও artifact generate করতে পারে।

এটি **Premiere automation helper**, Premiere replacement নয়। End-to-end import, sequence fidelity, effect parity, media relink এবং export verification করা হয়নি।

### 7.2 After Effects

বর্তমান bridge:

- ExtendScript composition rebuild করার চেষ্টা করে;
- AE manifest JSON তৈরি/পড়ে;
- `.aep/.aepx` read-only inspection করে।

এখানে full AE semantics—effects, expressions, masks, 3D cameras, shape layers, pre-comps, plug-ins, motion blur এবং render queue—সম্পূর্ণভাবে প্রতিস্থাপিত হয়নি।

### 7.3 DaVinci Resolve

Resolve bridge documented Python API এবং XML sidecar ব্যবহার করে। Source documentation নিজেই জানায় যে external scripting-এর জন্য Studio edition প্রয়োজন এবং free edition-এ সেই scripting surface নেই।

বর্তমান machine-এ Resolve পাওয়া যায়নি। তাই script syntax/source-level capability দেখা গেলেও actual Resolve execution বা render job success verified নয়।

### 7.4 CapCut

CapCut bridge-এর সবচেয়ে বড় সীমাবদ্ধতা:

- desktop draft format undocumented;
- `draft_content.json` structure version-specific;
- media folder manually populate করতে হয়;
- export-এর public scriptable API নেই;
- final export UI-তে manually করতে হয়;
- target CapCut build-এ generated draft load test হয়নি।

অতএব CapCut support status: **experimental draft interchange**, production integration নয়।

### 7.5 Krita

Krita bridge frame import/export, plugin source এবং audio sync intent-এর মতো helper দেয়। এটি 2D art workflow-এর সঙ্গে useful integration হতে পারে, কিন্তু Krita-কে NLE বা AE replacement হিসেবে গণ্য করা যাবে না।

---

## 8. Agent API, MCP, backend ও UI audit

### 8.1 Action registry

Runtime execution-এ বর্তমানে 19টি built-in action পাওয়া গেছে:

```text
bridge.detect
bridge.generate_script
bridge.inspect
bridge.list
checkpoint.diff
checkpoint.list
checkpoint.restore
checkpoint.save
compose.video
engine.route
environment.detect
inspect.frames
inspect.media
project.report
project.translate
project.validate
render.cartoon_frames
render.code_scene
timeline.diff
```

এটি agent-first design-এর শক্তিশালী অংশ। Typed parameters, output schemas, error codes, mutating flag এবং lazy optional imports ভালো সিদ্ধান্ত।

### 8.2 Documentation/schema drift

কিন্তু একই project-এ:

- `src/omniframe/agent/schemas/tools.json`-এ 18 actions লেখা;
- `AGENT_GUIDE.md`-এ full 18-action registry লেখা;
- backend module docstring-এ `18+` লেখা;
- runtime registry-তে 19 actions;
- Web UI overview-তে 19 লেখা।

এটি functional blocker না হলেও agent contract-এর জন্য গুরুত্বপূর্ণ documentation drift। একটি generated schema source-of-truth করা উচিত।

### 8.3 FastAPI backend

Backend-এ action execution, project validate/render, bridge list/detect, environment, update/restart, WebSocket activity এবং MCP call endpoint আছে। এটি local control surface হিসেবে কার্যকর।

Production deployment-এর আগে অনুপস্থিত/অপরীক্ষিত বিষয়:

- authentication এবং authorization;
- per-user/project isolation;
- path traversal এবং workspace sandbox;
- upload size/resource limits;
- background job queue;
- cancellation এবং retry policy;
- audit log persistence;
- rate limiting;
- secret/config management;
- remote deployment hardening।

### 8.4 Web UI

UI-তে dashboard, tool inspector, doctor status, render/bridge panel এবং live API calls আছে। কিন্তু এটি full NLE timeline editor নয়। Timeline drag/drop, clip trimming, keyframe graph, effect panel, audio waveform, proxy media এবং collaborative editing দেখা যায় না।

UI HTML-এ Tailwind CDN এবং Google Fonts external dependency আছে। Offline বা air-gapped deployment-এর জন্য assets vendoring বা local fallback দরকার।

---

## 9. Runtime এবং test findings

### 9.1 Environment doctor

এই machine-এ doctor result:

| Component | Result |
|---|---|
| OS | Windows 11 |
| Python | 3.12.10 |
| Node | v24.14.0 |
| FFmpeg | 8.1.1 |
| ffprobe | 8.1.1 |
| Chromium | 151.0.7922.34, Playwright-এর মাধ্যমে available |
| Native accelerator | unavailable; Python fallback |
| Premiere Pro | unavailable |
| After Effects | unavailable |
| DaVinci Resolve | unavailable |
| CapCut | unavailable |
| Krita | unavailable |

Doctor `ready: true` দিয়েছে। এর অর্থ core environment fallback সহ চালু হতে পারে; এটি production readiness বা host bridge success-এর প্রমাণ নয়।

### 9.2 সফল checks

নিম্নোক্ত checks সফল:

```powershell
$env:PYTHONPATH = 'src'; python -m compileall -q src
$env:PYTHONPATH = 'src'; python -m pytest -q tests/test_omniframe_promo_audio.py
$env:PYTHONPATH = 'src'; python -m pytest -q tests/test_handwashing_project.py tests/test_handwashing_render.py
$env:PYTHONPATH = 'src'; python -m omniframe.cli doctor --json
```

Action registry check-এ 19টি action পাওয়া গেছে।

### 9.3 Raw checkout import সমস্যা

`python -m pytest -q` raw checkout থেকে চালালে `ModuleNotFoundError: No module named 'omniframe'` হয়। কারণ project `src/` layout ব্যবহার করছে, কিন্তু editable install বা `PYTHONPATH=src` ছাড়া package import path-এ নেই।

এটি user-facing installation flow-এ editable install করলে এড়ানো যায়, কিন্তু contributor experience-এর জন্য নিচের একটি দরকার:

- `python -m pip install -e .` বাধ্যতামূলক development step;
- অথবা pytest config/packaging setup-এ src path সঠিকভাবে অন্তর্ভুক্ত করা;
- অথবা CI-তে explicit install step।

### 9.4 Source-path full suite failure

`PYTHONPATH=src` দিয়ে full suite চালালে একটি failure হয়েছে:

```text
tests/test_omniframe_promo_audio.py::test_generated_bed_is_stereo_48khz_and_30_seconds
assert 480000 == (48000 * 30)
```

Observed output-এ audio 48 kHz stereo হলেও 480,000 frames তৈরি হয়েছে, অর্থাৎ 10 seconds; test 30 seconds আশা করছে। Diagnosis অনুযায়ী:

- `examples/handwashing-2d/generate_audio.py`
- `examples/omniframe-promo/generate_audio.py`

দুটি top-level module একই নাম `generate_audio` ব্যবহার করছে। pytest module cache collision-এর ফলে wrong `generate_bed` import হচ্ছে। Individual test runs সফল হলেও combined suite deterministic নয়।

**Recommended fix:** example audio modules-কে unique package/module namespace-এ নেওয়া অথবা test import-কে explicit file/module path দিয়ে isolate করা; একই সঙ্গে audio duration contract এক জায়গায় canonical করা।

---

## 10. Security, safety এবং operational risks

ভালো দিক:

- proprietary binary patch বা DRM bypass করা হয়নি;
- bridge tiers ঝুঁকি প্রকাশ করে;
- missing dependency-তে structured degradation আছে;
- checkpoint/rollback surface আছে;
- subprocess usage-এ `shell=True` এড়ানোর project policy আছে।

যেসব risk production-এর আগে address করতে হবে:

1. **Arbitrary scene code:** HTML/JS rendering input untrusted হলে browser sandbox, filesystem/network policy এবং timeout boundary দরকার।
2. **Arbitrary paths:** project/asset path user-controlled হলে workspace restriction, symlink policy এবং path validation দরকার।
3. **Long-running FFmpeg jobs:** resource caps, cancellation, disk quota ও process cleanup দরকার।
4. **REST/MCP exposure:** local-only বনাম remote deployment স্পষ্ট করা এবং authentication যোগ করা দরকার।
5. **Generated host scripts:** script review, escaping, host version compatibility এবং explicit consent workflow দরকার।
6. **Undocumented CapCut format:** version pin, fixture corpus এবং compatibility warning দরকার।
7. **External CDN UI assets:** offline/reproducible build-এর জন্য vendoring দরকার।

---

## 11. Open-source alternative comparison

এখানে “open-source replacement” বলতে source-available বা unofficial clone নয়; official repository ও license-সহ যাচাইযোগ্য project বোঝানো হয়েছে। একটি project একই সঙ্গে অন্যটির পূর্ণ replacement নয়—প্রতিটির domain আলাদা।

| Project | প্রধান domain | License | OmniFrame-এর সঙ্গে সম্পর্ক | বাস্তব verdict |
|---|---|---|---|---|
| Motion Canvas | code-driven 2D motion graphics | MIT | agent-generated scene ও animation ধারণায় সবচেয়ে কাছাকাছি | OmniFrame-এর rendering engine নয়; complementary বা future adapter |
| Olive | non-linear video editing | GPL-3.0 | Premiere/CapCut-এর open-source NLE দিকের কাছাকাছি | full timeline editor চাইলে বেশি relevant |
| OpenToonz | 2D animation production | Modified BSD (main project; third-party পৃথক) | traditional 2D animation pipeline | cartoon authoring-এর জন্য শক্তিশালী, agent control plane নয় |
| Synfig | vector/cutout 2D animation | GPL-3.0 | rig/keyframe/vector animation | 2D animation-focused alternative |
| Natron | node-based compositing/VFX | GPL-2.0 | After Effects compositing/VFX দিকের কাছাকাছি | NLE নয়; compositing layer হিসেবে relevant |
| Manim Community | programmatic mathematical/explanatory animation | MIT | code-driven deterministic animation | educational motion graphics-এর জন্য useful, general NLE নয় |

### Official repositories

- Motion Canvas: <https://github.com/motion-canvas/motion-canvas>
- Olive: <https://github.com/olive-editor/olive>
- OpenToonz: <https://github.com/opentoonz/opentoonz>
- Synfig: <https://github.com/synfig/synfig>
- Natron: <https://github.com/NatronGitHub/Natron>
- Manim Community: <https://github.com/ManimCommunity/manim>

### গুরুত্বপূর্ণ correction

ব্যবহারকারীর উল্লেখিত “একজন developer-এর তৈরি open-source Adobe/CapCut version” কথাটির নির্দিষ্ট project name বা repository দেওয়া হয়নি। তাই নির্দিষ্ট নাম/লিংক ছাড়া সেই দাবিকে verified open-source alternative হিসেবে report করা যাবে না। উপরোক্ত তালিকাই official repository ও license-সহ যাচাইযোগ্য alternatives।

### কোনটি কোন কাজের জন্য বেশি উপযুক্ত

- **Motion Canvas-এর মতো programmatic motion graphics:** Motion Canvas বা Manim Community।
- **Premiere/CapCut-এর মতো timeline editing:** Olive; তবে maturity ও codec/effect parity আলাদাভাবে যাচাই করতে হবে।
- **Traditional 2D animation:** OpenToonz বা Synfig।
- **After Effects-এর compositing/VFX অংশ:** Natron; এটি AE-এর পূর্ণ replacement নয়।
- **AI-agent orchestration এবং multi-engine bridge:** OmniFrame-এর বর্তমান direction-ই আলাদা value proposition; উপরোক্ত tools কেউই একইভাবে universal agent control plane নয়।

---

## 12. OmniFrame-এর এখনো যা নেই

### Full NLE capability

- interactive timeline editing;
- clip trimming/ripple/roll/slip/slide;
- multicam editing;
- proxy/offline media workflow;
- waveform/beat editing;
- bins, search, metadata and media management;
- nested sequence/compound clip editing;
- full transition/effect browser;
- reliable export queue.

### Full After Effects capability

- composition/layer graph editor;
- expressions runtime;
- masks, mattes, shape layers;
- 2D/3D camera এবং lighting;
- plug-in ecosystem;
- motion tracking/roto;
- particle/physics ecosystem;
- render queue এবং cache management।

### Full production platform capability

- user authentication/RBAC;
- durable job orchestration;
- distributed workers;
- artifact/object storage;
- reproducible lockfile/container build;
- crash recovery and resumable remote jobs;
- cross-platform host CI;
- compatibility matrix for proprietary host versions;
- release artifacts and signed releases;
- telemetry/observability policy;
- formal backward compatibility policy for project schema।

---

## 13. Recommended roadmap

### Priority 0 — correctness এবং source-of-truth

1. Public repo, local remote এবং package metadata একীভূত করুন।
2. 18 বনাম 19 action drift ঠিক করুন এবং schema generated করুন।
3. `generate_audio` module collision ঠিক করুন।
4. Full test suite clean করুন।
5. CI-তে editable install এবং `PYTHONPATH`-independent test setup দিন।
6. project schema version এবং migration policy লিখুন।

### Priority 1 — production-safe control plane

1. workspace sandbox এবং path validation।
2. browser scene isolation, timeout, network policy এবং memory limit।
3. FFmpeg process cancellation/cleanup/resource quota।
4. persistent job model এবং background worker।
5. structured logs, artifact manifest এবং failure recovery।
6. API auth/RBAC—যদি localhost-এর বাইরে ব্যবহার হয়।

### Priority 2 — bridge reliability

1. প্রতিটি bridge-এর compatibility matrix তৈরি করুন।
2. minimal fixture project corpus রাখুন।
3. host-installed CI runner বা documented manual acceptance test দিন।
4. import/export round-trip score রিপোর্ট করুন।
5. CapCut format-এর জন্য version pin এবং fixture validation যোগ করুন।
6. Premiere/AE/Resolve output-কে “generated”, “import-tested”, “render-tested”—এই তিন status-এ আলাদা করুন।

### Priority 3 — user-facing creative surface

1. project browser এবং media asset manager।
2. visual timeline inspector/editor।
3. keyframe/easing editor।
4. audio waveform এবং subtitle editor।
5. preview cache/proxy system।
6. plugin/effect registry।

### Priority 4 — strategic positioning

OmniFrame-কে নিম্নোক্ত product statement-এ position করা সবচেয়ে সঠিক:

> “A typed, agent-first media orchestration layer that validates, renders, inspects, composes and translates projects across deterministic engines and external creative hosts.”

এটি “open-source Adobe clone” বা “CapCut replacement” বলার চেয়ে বেশি নির্ভুল এবং engineering roadmap-এর সঙ্গে সামঞ্জস্যপূর্ণ।

---

## 14. Final acceptance checklist

Production beta ঘোষণার আগে অন্তত নিচের checklist পূরণ করা উচিত:

- [ ] public repository এবং local checkout একই commit lineage-এ;
- [ ] 19 action-এর generated schema/guide/UI consistency;
- [ ] raw checkout থেকে clean install এবং test;
- [ ] full pytest suite pass;
- [ ] Playwright golden-frame regression;
- [ ] StubBackend স্পষ্ট degraded status সহ রাখা;
- [ ] native accelerator-এর supported/unsupported matrix;
- [ ] FFmpeg codec/container/audio/subtitle matrix;
- [ ] 10 মিনিট ও 1 ঘণ্টা render soak test;
- [ ] checkpoint/restore corruption test;
- [ ] malicious path এবং untrusted JS test;
- [ ] API auth বা localhost-only guarantee;
- [ ] Premiere import acceptance test;
- [ ] After Effects script acceptance test;
- [ ] Resolve Studio script acceptance test;
- [ ] CapCut target-version draft load/export acceptance test;
- [ ] Krita workflow acceptance test;
- [ ] release artifact, changelog, versioning এবং rollback plan।

---

## 15. Final verdict

OmniFrame Studio “perfectly complete” নয়, এবং সব advertised creative software-এর open-source replacementও নয়। এটি একটি **বাস্তব, modular, agent-first alpha foundation**—বিশেষ করে typed actions, universal timeline, deterministic rendering, FFmpeg composition, inspection এবং bridge generation-এর জন্য।

বর্তমান release-এর সবচেয়ে বড় value হলো **orchestration এবং interoperability**; সবচেয়ে বড় gap হলো **full-fidelity host integration, interactive editing, production hardening এবং repeatable end-to-end verification**।

**Recommendation:** এখনই full NLE clone বানানোর দাবি না করে প্রথমে agent control plane ও interchange layer-কে production-grade করুন। তারপর একটি নির্দিষ্ট vertical—যেমন code-video + 2D cartoon + FFmpeg export—কে stable beta হিসেবে freeze করুন। Premiere/After Effects/CapCut support-কে পৃথক experimental bridge tier হিসেবে document করুন।

---

## Appendix A — audited source references

Local source evidence:

- `README.md:1-3, 42-77, 85-129, 137-156`
- `pyproject.toml:5-40, 43-59`
- `src/omniframe/engines/code_video/backends.py:1-16, 129-183, 454-575`
- `src/omniframe/bridges/base.py:8-20, 42-48, 121-147, 216-224`
- `src/omniframe/bridges/capcut.py:1-7, 82-115, 117-199`
- `src/omniframe/bridges/davinci_resolve.py:1-13, 90-141, 169-198`
- `src/omniframe/core/timeline_schema/translate.py:178-185, 432-453, 545-548, 690-693, 783-789`
- `src/omniframe/backend/server.py:1-4, 101-157, 180-250, 252-344`
- `src/omniframe/ui/index.html:1-10, 507-530, 710-750`
- `src/omniframe/agent/schemas/tools.json:3-6`
- `tests/` focused bridge, engine, compositor, runtime এবং project tests

External repository references:

- OmniFrame public repository: <https://github.com/amitkumardas3624/omniframe-studio>
- Motion Canvas: <https://github.com/motion-canvas/motion-canvas>
- Olive: <https://github.com/olive-editor/olive>
- OpenToonz: <https://github.com/opentoonz/opentoonz>
- Synfig: <https://github.com/synfig/synfig>
- Natron: <https://github.com/NatronGitHub/Natron>
- Manim Community: <https://github.com/ManimCommunity/manim>
