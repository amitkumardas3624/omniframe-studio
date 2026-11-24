"""The root agent skill document must stay parseable and free of stray glyphs.

SKILL.md is the contract a CLI agent loads before it touches a project. A
corrupted character inside a word, a lost BOM, or an unclosed frontmatter fence
is invisible in review and silently breaks the agent, so it is checked here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"

FENCE = "`" * 3

# Printable ASCII plus the typographic marks the document may use.
EXTRA = "§·→—≤≥±×…≈≠⇒−Δζ"


def _read() -> str:
    """Read the document with normalized newlines, whatever the checkout did."""

    return SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_skill_uses_only_allowed_characters() -> None:
    text = _read()

    allowed = {chr(code) for code in range(0x20, 0x7F)}
    allowed.update({"\t", "\r", "\n"})
    allowed.update(EXTRA)

    offenders = sorted({char for char in text if char not in allowed})
    assert offenders == [], [hex(ord(char)) for char in offenders]


def test_skill_frontmatter_is_a_parseable_ascii_yaml_subset() -> None:
    text = _read()
    assert text.startswith("---\n")

    _, frontmatter, _body = text.split("---", 2)

    keys = re.findall(r"^([a-z_]+):", frontmatter, re.MULTILINE)

    assert keys == ["name", "description", "triggers"]
    assert re.search(r"^name: [a-z0-9-]+$", frontmatter, re.MULTILINE)
    assert frontmatter.count('"') % 2 == 0
    assert len(re.findall(r"^  - \S", frontmatter, re.MULTILINE)) >= 20


def test_skill_json_examples_parse() -> None:
    text = _read()
    blocks = re.findall(FENCE + r"json\n(.*?)" + FENCE, text, re.DOTALL)

    assert blocks, "expected at least one json example"
    for block in blocks:
        json.loads(block)
