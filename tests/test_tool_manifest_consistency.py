import json
from pathlib import Path

from omniframe.core.agent_runtime.actions import ensure_builtin_actions

MANIFEST = Path(__file__).parents[1] / "src/omniframe/agent/schemas/tools.json"
ROOT_GUIDE = Path(__file__).parents[1] / "AGENT_GUIDE.md"
AGENT_GUIDE = Path(__file__).parents[1] / "src/omniframe/agent/AGENT_GUIDE.md"
AGENT_SKILL = Path(__file__).parents[1] / "src/omniframe/agent/SKILL.md"
AGENT_README = Path(__file__).parents[1] / "src/omniframe/agent/README.md"
BACKEND_SERVER = Path(__file__).parents[1] / "src/omniframe/backend/server.py"


def test_committed_tool_manifest_matches_runtime():
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runtime = ensure_builtin_actions().to_json_document()
    assert committed == runtime


def test_guides_do_not_claim_eighteen_actions_or_stale_action_names():
    text = ROOT_GUIDE.read_text(encoding="utf-8") + AGENT_GUIDE.read_text(encoding="utf-8")
    assert "18-action" not in text
    assert "all 18 actions" not in text
    assert "project.render" not in text
    assert "project.compose" not in text
    assert "render.code_scene" in text
    assert "compose.video" in text
    assert '"html"' in text
    assert '"output_dir"' in text
    assert '"frames"' in text
    assert '"output"' in text


def test_agent_docs_use_runtime_manifest_wording_and_current_error_codes():
    skill_text = AGENT_SKILL.read_text(encoding="utf-8")
    readme_text = AGENT_README.read_text(encoding="utf-8")
    guide_text = AGENT_GUIDE.read_text(encoding="utf-8")

    for text in (skill_text, readme_text):
        assert "18 registered actions" not in text
        assert "18-action" not in text
        assert "all 18 actions" not in text
    assert "18 built-in actions" not in skill_text

    assert "the current generated tool manifest" in skill_text
    assert "the current generated tool manifest" in readme_text
    assert "E_DEPENDENCY_MISSING" in guide_text


def test_docs_do_not_claim_stale_test_count_cartoon_seed_or_action_count():
    skill_text = AGENT_SKILL.read_text(encoding="utf-8")
    server_text = BACKEND_SERVER.read_text(encoding="utf-8")

    assert "128 tests" not in skill_text
    assert "18+ agent actions" not in server_text

    determinism = skill_text.split("## Determinism Strategy", 1)[1].split("## Error Model", 1)[0]
    assert "cartoon_frames" not in determinism
    assert "code_scene" in determinism


def test_current_builtin_action_names_are_stable():
    assert ensure_builtin_actions().names() == [
        "bridge.detect",
        "bridge.generate_script",
        "bridge.inspect",
        "bridge.list",
        "checkpoint.diff",
        "checkpoint.list",
        "checkpoint.restore",
        "checkpoint.save",
        "compare.frames",
        "compose.video",
        "engine.route",
        "environment.detect",
        "inspect.frames",
        "inspect.media",
        "project.report",
        "project.translate",
        "project.validate",
        "render.cartoon_frames",
        "render.code_scene",
        "timeline.diff",
    ]
