"""Tests for the agent runtime: registry, router, checkpoints and inspection."""

from __future__ import annotations

import json

import pytest

from omniframe.core.agent_runtime.checkpoint import CheckpointStore, diff_projects
from omniframe.core.agent_runtime.inspect import (
    build_contact_sheet,
    frame_strip,
    list_image_frames,
    timeline_report,
)
from omniframe.core.agent_runtime.registry import (
    ActionRegistry,
    ActionSpec,
    validate_against_schema,
)
from omniframe.core.agent_runtime.router import EngineRouter, RoutingRequest
from omniframe.core.timeline_schema.models import (
    Clip,
    ClipKind,
    OmniProject,
    ProjectMeta,
    Track,
    TrackKind,
)


def make_project(name: str = "demo") -> OmniProject:
    project = OmniProject(meta=ProjectMeta(name=name, fps=30))
    project.tracks.append(
        Track(
            id="v1",
            kind=TrackKind.VIDEO,
            clips=[
                Clip(
                    id="c1",
                    name="Intro",
                    kind=ClipKind.VIDEO,
                    start_frame=0,
                    duration_frames=60,
                    source="a.mp4",
                )
            ],
        )
    )
    return project


class TestRegistry:
    def test_register_and_execute(self):
        registry = ActionRegistry()
        registry.register(
            ActionSpec(
                name="demo.echo",
                description="Echo the payload.",
                input_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string", "default": "hi"}},
                },
                handler=lambda value="hi": {"echoed": value},
            )
        )
        assert registry.has("demo.echo")
        assert registry.execute("demo.echo", {}) == {"echoed": "hi"}
        assert registry.execute("demo.echo", {"value": "yo"}) == {"echoed": "yo"}

    def test_unknown_action_raises(self):
        from omniframe.core.errors import ToolNotFound

        with pytest.raises(ToolNotFound):
            ActionRegistry().execute("nope")

    def test_invalid_arguments_raise(self):
        from omniframe.core.errors import ValidationError

        registry = ActionRegistry()
        registry.register(
            ActionSpec(
                name="demo.strict",
                description="Needs a number.",
                input_schema={
                    "type": "object",
                    "properties": {"count": {"type": "integer"}},
                    "required": ["count"],
                },
                handler=lambda count: {"count": count},
            )
        )
        with pytest.raises(ValidationError):
            registry.execute("demo.strict", {"count": "not-a-number"})
        with pytest.raises(ValidationError):
            registry.execute("demo.strict", {})

    def test_handler_errors_are_wrapped(self):
        from omniframe.core.errors import ActionError

        registry = ActionRegistry()
        registry.register(
            ActionSpec(
                name="demo.boom",
                description="Always fails.",
                handler=lambda: (_ for _ in ()).throw(RuntimeError("nope")),
            )
        )
        with pytest.raises(ActionError):
            registry.execute("demo.boom", {})

    def test_tool_schema_shape(self):
        registry = ActionRegistry()
        registry.register(
            ActionSpec(name="demo.x", description="d", input_schema={"type": "object"})
        )
        schema = registry.to_tool_schemas()[0]
        assert schema["name"] == "demo.x"
        assert "inputSchema" in schema and "meta" in schema

    def test_builtin_actions_are_registered(self):
        from omniframe.core.agent_runtime.actions import ensure_builtin_actions

        registry = ensure_builtin_actions()
        assert registry.has("environment.detect")
        assert registry.has("project.validate")
        assert registry.has("render.code_scene")
        document = registry.to_json_document()
        assert document["kind"] == "omniframe_tool_manifest"
        json.dumps(document)


class TestSchemaValidation:
    def test_defaults_are_injected(self):
        target: dict = {}
        errors = validate_against_schema(
            target, {"type": "object", "properties": {"n": {"type": "integer", "default": 7}}}
        )
        assert errors == []
        assert target["n"] == 7

    def test_enum_and_range(self):
        errors = validate_against_schema(
            {"a": "z"}, {"type": "object", "properties": {"a": {"enum": ["x", "y"]}}}
        )
        assert errors

    def test_additional_properties_rejected(self):
        errors = validate_against_schema(
            {"a": 1, "b": 2},
            {"type": "object", "properties": {"a": {}}, "additionalProperties": False},
        )
        assert errors


class TestRouter:
    def test_routes_to_code_engine_for_code_capability(self):
        router = EngineRouter(available_capabilities={"chromium", "ffmpeg"})
        choice = router.route(RoutingRequest(capability="code_scene"))
        assert choice.engine == "code_html_js"
        assert choice.available

    def test_unavailable_host_is_reported(self):
        router = EngineRouter(available_capabilities={"chromium", "ffmpeg"})
        choice = router.route(RoutingRequest(capability="nle_timeline"))
        assert choice.available is False
        assert "premiere_pro" in choice.reason

    def test_preference_is_honoured(self):
        router = EngineRouter(available_capabilities={"chromium", "ffmpeg", "capcut"})
        choice = router.route(RoutingRequest(preferred_engine="capcut"))
        assert choice.engine == "capcut"

    def test_describe_lists_every_engine(self):
        router = EngineRouter(available_capabilities=set())
        described = router.describe()
        assert {entry["id"] for entry in described} >= {
            "code_html_js",
            "cartoon_2d",
            "ffmpeg_compositor",
            "after_effects",
            "premiere_pro",
            "davinci_resolve",
            "capcut",
        }


class TestCheckpoints:
    def test_save_and_restore(self, tmp_path):
        store = CheckpointStore(tmp_path)
        checkpoint = store.save(make_project(), label="before-edit")
        assert checkpoint.id in [c.id for c in store.list()]
        restored = store.load(checkpoint.id)
        assert restored.meta.name == "demo"

    def test_diff_detects_changes(self, tmp_path):
        store = CheckpointStore(tmp_path)
        before = store.save(make_project(), label="a")
        changed = make_project()
        changed.tracks[0].clips[0].duration_frames = 90
        after = store.save(changed, label="b")
        report = store.diff(before.id, after.id)
        assert report["identical"] is False
        assert report["changed_clips"]

    def test_restore_writes_file(self, tmp_path):
        store = CheckpointStore(tmp_path)
        checkpoint = store.save(make_project())
        target = tmp_path / "restored.json"
        store.restore(checkpoint.id, target)
        assert target.exists()

    def test_unknown_checkpoint_raises(self, tmp_path):
        from omniframe.core.errors import CheckpointError

        with pytest.raises(CheckpointError):
            CheckpointStore(tmp_path).load("nope")


class TestInspection:
    def _frames(self, tmp_path, count=4):
        from PIL import Image

        frames = []
        for index in range(count):
            path = tmp_path / f"frame_{index:06d}.png"
            Image.new("RGBA", (64, 36), (index * 20, 40, 60, 255)).save(path)
            frames.append(path)
        return frames

    def test_contact_sheet(self, tmp_path):
        frames = self._frames(tmp_path)
        sheet = build_contact_sheet(frames, tmp_path / "sheet.png", columns=2)
        assert sheet.exists() and sheet.stat().st_size > 0

    def test_frame_strip(self, tmp_path):
        frames = self._frames(tmp_path)
        strip = frame_strip(frames, tmp_path / "strip.png")
        assert strip.exists() and strip.stat().st_size > 0

    def test_list_image_frames(self, tmp_path):
        self._frames(tmp_path)
        assert len(list_image_frames(tmp_path)) == 4

    def test_timeline_report(self):
        report = timeline_report(make_project())
        assert report["fps"] == 30
        assert report["tracks"][0]["clips"][0]["id"] == "c1"

    def test_project_diff_helper(self):
        a = make_project()
        b = make_project()
        b.tracks[0].clips[0].duration_frames = 120
        report = diff_projects(a, b)
        assert report["identical"] is False
