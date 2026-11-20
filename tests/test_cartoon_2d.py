"""Tests for the 2D cartoon engine."""

from __future__ import annotations

import pytest

from omniframe.engines.cartoon_2d import (
    CartoonScene,
    Easing,
    Keyframe,
    Layer,
    build_contact_sheet,
    build_xsheet,
    evaluate_layer,
    evaluate_scene,
    interpolate,
    render_frame,
    render_frames,
    tween_value,
)
from omniframe.engines.cartoon_2d.bridge import get_bridge


class TestTween:
    def test_linear(self):
        assert tween_value(0, 10, 0.5) == pytest.approx(5)
        assert tween_value(0, 10, 0.0) == pytest.approx(0)

    def test_ease_in_out(self):
        assert tween_value(0, 10, 0.5, "ease_in_out") == pytest.approx(5)
        assert tween_value(0, 10, 0.25, "ease_in_out") < 2.5

    def test_hold_and_step(self):
        assert tween_value(0, 10, 0.9, "hold") == pytest.approx(0)
        assert tween_value(0, 10, 0.6, Easing("step", steps=4)) == pytest.approx(5)

    def test_interpolate_sequences_and_mappings(self):
        assert interpolate([0, 0], [10, 20], 0.5) == pytest.approx([5, 10])
        merged = interpolate({"x": 0}, {"x": 10}, 0.5)
        assert merged["x"] == pytest.approx(5)

    def test_unknown_easing_raises(self):
        with pytest.raises(ValueError):
            Easing.from_value("wobble")


class TestEvaluate:
    def test_static_layer(self):
        layer = Layer(id="a", x=10, y=20)
        props = evaluate_layer(layer, 5)
        assert props["x"] == pytest.approx(10)
        assert props["y"] == pytest.approx(20)

    def test_single_keyframe_holds(self):
        layer = Layer(id="a", x=0, keyframes=[Keyframe(frame=10, values={"x": 100})])
        assert evaluate_layer(layer, 0)["x"] == pytest.approx(100)
        assert evaluate_layer(layer, 50)["x"] == pytest.approx(100)

    def test_two_keyframes_interpolate(self):
        layer = Layer(
            id="a",
            x=0,
            keyframes=[Keyframe(frame=0, values={"x": 0}), Keyframe(frame=10, values={"x": 100})],
        )
        assert evaluate_layer(layer, 5)["x"] == pytest.approx(50)

    def test_property_without_keyframe_keeps_static_value(self):
        layer = Layer(id="a", y=42, keyframes=[Keyframe(frame=0, values={"x": 1})])
        assert evaluate_layer(layer, 3)["y"] == pytest.approx(42)

    def test_camera_keyframes(self):
        scene = CartoonScene(
            width=100,
            height=100,
            camera_x=0,
            camera_keyframes=[
                Keyframe(frame=0, values={"x": 0}),
                Keyframe(frame=10, values={"x": 100}),
            ],
        )
        state = evaluate_scene(scene, 5)
        assert state["camera"]["x"] == pytest.approx(50)


class TestRendering:
    def _scene(self) -> CartoonScene:
        return CartoonScene(
            width=64,
            height=36,
            background="#000000FF",
            duration_frames=3,
            layers=[
                Layer(id="solid", kind="solid", color="#FF3366FF", x=10, y=10, z=1),
                Layer(id="hidden", kind="solid", color="#FFFFFFFF", visible=False),
            ],
        )

    def test_render_frame_writes_png(self, tmp_path):
        path = render_frame(self._scene(), 0, tmp_path / "f0.png")
        assert path.exists()

    def test_solid_layer_changes_pixels(self, tmp_path):
        from PIL import Image

        scene = self._scene()
        path = render_frame(scene, 0, tmp_path / "f0.png")
        with Image.open(path) as image:
            pixel = image.convert("RGBA").getpixel((20, 20))
        assert pixel == (255, 51, 102, 255)

    def test_hidden_layer_is_not_drawn(self, tmp_path):
        from PIL import Image

        scene = CartoonScene(
            width=32,
            height=32,
            background="#000000FF",
            duration_frames=1,
            layers=[Layer(id="hidden", kind="solid", color="#FFFFFFFF", visible=False)],
        )
        path = render_frame(scene, 0, tmp_path / "f0.png")
        with Image.open(path) as image:
            pixel = image.convert("RGBA").getpixel((16, 16))
        assert pixel[:3] == (0, 0, 0)

    def test_render_frames_writes_sequence(self, tmp_path):
        frames = render_frames(self._scene(), tmp_path / "frames")
        assert len(frames) == 3
        assert frames[0].name == "frame_000000.png"
        assert all(path.exists() for path in frames)

    def test_resume_does_not_rewrite(self, tmp_path):
        target = tmp_path / "frames"
        render_frames(self._scene(), target)
        first = target / "frame_000000.png"
        stamp = first.stat().st_mtime_ns
        render_frames(self._scene(), target, resume=True)
        assert first.stat().st_mtime_ns == stamp

    def test_contact_sheet(self, tmp_path):
        frames = render_frames(self._scene(), tmp_path / "frames")
        sheet = build_contact_sheet(frames, tmp_path / "sheet.png", columns=3)
        assert sheet.exists() and sheet.stat().st_size > 0


class TestXSheet:
    def test_csv_has_a_row_per_layer(self, tmp_path):
        scene = CartoonScene(
            width=32,
            height=32,
            duration_frames=4,
            layers=[Layer(id="a", kind="solid"), Layer(id="b", kind="solid")],
        )
        path = build_xsheet(scene, tmp_path / "x.csv")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0].startswith("layer")
        assert len(lines) >= 3  # header + 2 layers + camera/dialogue rows

    def test_markdown_format(self, tmp_path):
        scene = CartoonScene(width=32, height=32, duration_frames=2)
        path = build_xsheet(scene, tmp_path / "x.md", fmt="markdown")
        assert path.read_text(encoding="utf-8").startswith("| layer |")


class TestDrawingBridge:
    def test_krita_detect_never_raises(self):
        bridge = get_bridge("krita")
        report = bridge.detect()
        assert "installed" in report

    def test_unknown_bridge_raises(self):
        with pytest.raises(KeyError):
            get_bridge("nope")

    def test_import_and_export_frames(self, tmp_path):
        from PIL import Image

        frames = []
        for index in range(3):
            path = tmp_path / f"src_{index}.png"
            Image.new("RGBA", (16, 16), (index * 30, 0, 0, 255)).save(path)
            frames.append(path)

        bridge = get_bridge("krita")
        document = tmp_path / "doc"
        result = bridge.import_frames(frames, document)
        assert result["imported"] == 3

        exported = bridge.export_frames(document, tmp_path / "out")
        assert exported["exported"] == 3

    def test_plugin_script_is_written(self, tmp_path):
        bridge = get_bridge("krita")
        plugin = bridge.write_plugin(tmp_path / "doc")
        assert plugin.exists()
        assert "Krita" in plugin.read_text(encoding="utf-8")

    def test_sync_audio(self, tmp_path):
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF")
        bridge = get_bridge("krita")
        result = bridge.sync_audio(audio, tmp_path / "doc")
        assert result["available"] is True
