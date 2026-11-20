from __future__ import annotations

import pytest

from omniframe._native import native_available
from omniframe.core.errors import EngineUnavailable
from omniframe.engines.cartoon_2d import CartoonScene, Layer, render_frame


def _scene() -> CartoonScene:
    return CartoonScene(
        width=64,
        height=36,
        background="#00000000",
        duration_frames=1,
        layers=[
            Layer(id="solid", kind="solid", color="#FF0000FF", x=20, y=18),
            Layer(id="vector", kind="vector", color="#00FF00FF", x=44, y=18),
        ],
    )


def test_auto_backend_matches_python_for_supported_scene(tmp_path):
    scene = _scene()
    python_path = render_frame(scene, 0, tmp_path / "python.png", backend="python")
    auto_path = render_frame(scene, 0, tmp_path / "auto.png", backend="auto")
    from PIL import Image

    with Image.open(python_path) as python_image, Image.open(auto_path) as auto_image:
        assert python_image.size == auto_image.size == (64, 36)
    if not native_available():
        assert python_path.read_bytes() == auto_path.read_bytes()


def test_native_request_is_actionable_without_extension(tmp_path):
    if native_available():
        pytest.skip("native extension is installed in this environment")
    with pytest.raises(EngineUnavailable):
        render_frame(_scene(), 0, tmp_path / "native.png", backend="native")


def test_auto_backend_falls_back_for_text_scene(tmp_path):
    scene = CartoonScene(
        width=64,
        height=36,
        duration_frames=1,
        layers=[Layer(id="text", kind="text", name="hello", color="#FFFFFFFF")],
    )
    path = render_frame(scene, 0, tmp_path / "text.png", backend="auto")
    assert path.exists()
