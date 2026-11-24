# External skill manifest

A snapshot of the third-party agent skills that were inspected while the root
`SKILL.md` was being synthesised. It exists so the investigation can be
reproduced or audited later without anyone re-running a network install on
guesswork.

## What this file is, and is not

- It **is** a record of provenance: where each payload came from, what the
  installer did, how many files arrived, how large they were, and a digest of
  the exact bytes.
- It **is not** a vendoring of that code. No file from any of these payloads is
  tracked in this repository. `.claude/` and `.agents/` are not part of our tree.
- It **is not** a licence review, a security clearance, or an endorsement.
  Digests prove what arrived; they say nothing about whether it is safe to run.
  Read the upstream `LICENSE` before you reuse anything.
- Nothing here was executed. No render in this project depends on these skills.

## Method

- Installer: the `skills` CLI, run as `npx -y skills@latest`. It installs an
  agent skill into a per-agent directory in **copy** mode.
- Target: a throwaway directory outside the repository, so experiment output
  cannot be mistaken for project content:
  `$env:TEMP\omniframe-skill-probe\<source>\.claude\skills\<skill>`
- Each payload arrived as `<skill>/SKILL.md` plus optional supporting files
  (references, scripts, fonts, examples).
- Digests: for every file in a skill directory we take its POSIX-style relative
  path, its size in bytes, and the lowercase SHA-256 of its content. Each line
  is `relpath<TAB>bytes<TAB>sha256`; lines are sorted by relative path with
  ordinal (case-sensitive) comparison, joined with `LF` and **no** trailing
  newline, UTF-8 encoded, then hashed once with SHA-256. The number below is
  the first 32 hex characters. Recomputing it from the same tree with this
  recipe reproduces it exactly, and any edited byte changes it.

## Sources

| # | Source | Command as written in the brief | Outcome |
|---|---|---|---|
| 1 | `MengTo/Skills` | `npx skills add MengTo/Skills --skill html-demo` | 1 skill installed |
| 2 | `Rieranthony/product-film-skill` | `/plugin marketplace add Rieranthony/product-film-skill` then `/plugin install product-film@product-film-skill` | **Not executable** in a shell: Claude Code slash commands |
| 3 | `buildfastwithai/buildfast-skills` | `npx skills@latest add https://github.com/buildfastwithai/buildfast-skills` | 8 skills installed, 1 skipped by the installer |

Source 1 also skipped every `agent-skills/...` entry it tried, each with the same
YAML error: the repository's frontmatter uses an unquoted `description` that
contains a colon, and the parser reads the remainder as a nested mapping.

Source 2 is not a URL failure. `/plugin` is a command of the Claude Code
interface, not an executable on `PATH`; the pair has to be typed inside a live
Claude Code session, so a plain shell cannot run it and this manifest cannot
claim it was tested.

Source 3's skip is the interesting one and is recorded in full below: one skill
out of nine is unusable as published.

## Installed payloads

| Source | Skill | Files | Bytes | Digest (sha256, first 32) |
|---|---|---|---|---|
| `MengTo/Skills` | `html-demo` | 17 | 280,590 | `36581fc7d26cc9a1744344db4f3894a7` |
| `buildfastwithai/buildfast-skills` | `crazy-ecommerce-builder-skill` | 10 | 78,742 | `912aa0cb28eea0ee37280edaa9798fc8` |
| `buildfastwithai/buildfast-skills` | `create-svg` | 68 | 3,073,934 | `94c1e42531b87b208fbe633e99e321ca` |
| `buildfastwithai/buildfast-skills` | `godot-web-3d-demo-skill` | 3 | 18,454 | `d41460f1e0dc91fda0a9902802b272a9` |
| `buildfastwithai/buildfast-skills` | `landing-page-generator-skill` | 12 | 100,014 | `4f1e4332b4b8c8d1ed4bde64e2c1187d` |
| `buildfastwithai/buildfast-skills` | `motion-studio` | 126 | 3,398,040 | `eb9af939b3eec63a09624f0d2657914b` |
| `buildfastwithai/buildfast-skills` | `premium-ui-revamp-skill` | 6 | 45,721 | `75dcf894d1dbd73020d18af132238088` |
| `buildfastwithai/buildfast-skills` | `talking-avatar-skill` | 16 | 129,189 | `d7b2b89de40561dee05b5657eaed567b` |
| `buildfastwithai/buildfast-skills` | `threejs-game-generator-skill` | 8 | 85,387 | `3e4218b5a606c1fe1c91544839ca63e1` |

Totals: 9 skills, 266 files, 7,210,071 bytes. Two payloads dominate:
`create-svg` and `motion-studio`; together they are most of the download.

## The skipped skill

`generative-film-skill` did not install. The installer reported, verbatim:

```text
[SKILLS_SKILL_SKIPPED] .../generative-film-skill/SKILL.md
  YAML parse error: Nested mappings are not allowed in compact mappings at line 2, column 14
```

Diagnosis: its frontmatter has an unquoted `description:` value containing `: `,
so a YAML parser reads that as the start of a nested mapping. The fix is a pair
of quotes:

```yaml
description: "one line here: even with a colon in it"
```

This is a bug in the published file, not in our pipeline, and not something to
patch on the author's behalf. Treat the skill as unavailable until upstream
fixes it.

## Third-party safety signals

The installer grades payloads and, for some, consults external scanners. Report
them as they are; do not launder them into "safe":

| Skill | Signal |
|---|---|
| `motion-studio` | Gen **medium**; Socket **2 alerts**; Snyk low |
| `godot-web-3d-demo-skill` | Snyk **medium** |
| the other 7 | safe or low |

A "medium" here is not a verdict that something is malicious; it is also not
clearance. Nine agent skills that can drive a browser and write files are nine
new things that run with your privileges. Because of that, none of them were run
against this repository, and none are vendored into it.

## Reproduce

```powershell
$root = Join-Path $env:TEMP 'omniframe-skill-probe'
New-Item -ItemType Directory -Force -Path $root | Out-Null
Push-Location $root
npx -y skills@latest add MengTo/Skills --skill html-demo --agent claude-code -y --json
npx -y skills@latest add https://github.com/buildfastwithai/buildfast-skills --agent claude-code -y --json
Pop-Location
Get-ChildItem -Path $root -Recurse -Filter SKILL.md
```

Two traps worth knowing, both hit during this run:

- `--list` (`-l`) is **not** a dry run you can trust in a script. It still shows an
  interactive picker, so with no TTY it hangs instead of printing. To find out
  what a source contains, install it into a throwaway directory with `-y --json`.
- The installer is interactive by default. Always pass `-y --json` when the
  output will be captured, or the process will wait for a keypress that never
  arrives.

## What the synthesis took from this

The master skill at the repository root does not copy these payloads. It
distils four ideas it did not previously have, and every one of them is written
as a rule the renderer can enforce rather than as advice:

| Idea | Where it lands |
|---|---|
| A film is one through-line object under continuous transformation; a cut is a failure to transform | `SKILL.md` section 4 (P2), section 6A (Cuts) |
| Time is quantised to `frame / fps`; nothing integrates, nothing accumulates | section 10, law 1 |
| Motion blur is sampled from subframes and blended by velocity, not faked with a blur filter | section 10, law 4 |
| Look at one frame per beat before you pay for the whole render | section 11, the pre-render gate |

The rest of the borrowed material (style catalogues, template lists) was
left out on purpose: a catalogue is a menu to pick from, and a skill that lets an
agent pick from a menu produces the template look all three sources forbid.

## Refreshing this snapshot

If you re-run the installs, recompute the digests and update the table in one
pass; a partial update makes the manifest worse than absent. Add a row only for
a payload you actually inspected, and say what you inspected it for.
