# Repository identity

Status: **RESOLVED — 2026-11-22.**

The canonical release source is
`https://github.com/amitkumardas3624/omniframe-studio`.

The mismatch recorded in Phase 0 was caused by a GitHub **username change**: the old
slug `gbd718106-cmyk/omniframe-studio` remained embedded in the remote, the installers,
the README and the package metadata. The user confirmed the new username and selected the
canonical URL; every surface was then updated to agree. Nothing was rewritten before that
decision, and nothing was rewritten to a value the user did not name.

## Values observed before the decision

- **User-provided public repository:** `https://github.com/amitkumardas3624/omniframe-studio`
- **Local configured remote (`origin`):** `https://github.com/gbd718106-cmyk/omniframe-studio.git` (fetch and push)
- **README/installer source:** `https://github.com/gbd718106-cmyk/omniframe-studio.git`
- **`install.ps1` / `install.sh` default:** `https://github.com/gbd718106-cmyk/omniframe-studio.git`
- **`pyproject.toml` project URLs:** `https://github.com/omniframe-studio/omniframe-studio`
  - `Homepage`
  - `Documentation` → `.../tree/main/docs`
  - `Issues`
- **Default branch:** `master`

Three distinct identifiers appeared across the project:

| Surface | Value |
| --- | --- |
| User-provided | `amitkumardas3624/omniframe-studio` |
| Git remote + installers | `gbd718106-cmyk/omniframe-studio` |
| Package metadata (`pyproject.toml`) | `omniframe-studio/omniframe-studio` |

Additional drift: the `pyproject.toml` `Documentation` URL pointed to `tree/main`, while the
repository default branch is `master`.

## Decision taken

The user named `https://github.com/amitkumardas3624/omniframe-studio` as canonical on
2026-11-22 and authorized propagating it to every surface.

The work was committed and pushed to the `omniframe-platform-hardening` branch and then
fast-forwarded into `master`. The fast-forward was verified before pushing: the remote's `master`
(`4759e40`) is an ancestor of the local `master` (`6749271`), which is in turn an ancestor of the
hardening commit (`e430266`). So `master` advanced by 9 commits with **no history rewritten and no
force push** — the old slug was the same project under the old username, not a divergent history.

## Surfaces updated

| Surface | Change |
| --- | --- |
| git remote `origin` (fetch + push) | `git remote set-url origin https://github.com/amitkumardas3624/omniframe-studio.git` |
| `install.sh` | usage comment + default `REPO_URL` |
| `install.ps1` | usage comment + default `$repoUrl` |
| `README.md` | both one-line install commands |
| `SKILL.md` | both one-line install commands |
| `pyproject.toml` `[project.urls]` | `Homepage`, `Documentation`, `Issues` |
| `pyproject.toml` `Documentation` branch | `tree/main` → `tree/master` (the repository's default branch) |
| `src/omniframe/updater.py` | `DEFAULT_REPO_SLUG` → `amitkumardas3624/omniframe-studio` |
| `src/omniframe/backend/server.py` | fallback "Web UI not yet built" link |
| `tests/test_installers.py` | assertions updated, plus a new drift guard |

## Guard added

`tests/test_installers.py` now fails if any live surface
(`install.sh`, `install.ps1`, `README.md`, `SKILL.md`, `pyproject.toml`,
`src/omniframe/updater.py`, `src/omniframe/backend/server.py`) contains a stale slug
(`gbd718106-cmyk/omniframe-studio` or `omniframe-studio/omniframe-studio`) or omits the
canonical one, and a second test asserts the `Documentation` URL still points at
`tree/master/docs` and not `tree/main`. A future rename cannot silently reintroduce the
same class of drift.

## Standing rule

If a mismatch reappears, stop and ask which URL is canonical. Never rewrite a URL
unilaterally, and never publish while the surfaces disagree — the whole point of this
record is that publishing to the wrong project sends users to a repository that does not
control the release.
