from __future__ import annotations


def test_native_import_is_optional():
    from omniframe._native import native_status

    status = native_status()
    assert status["mode"] in {"native", "fallback"}


def test_native_api_has_fallback_shape():
    from omniframe._native import native_api

    assert hasattr(native_api, "FramePipeSink")
    assert hasattr(native_api, "CartoonRasterizer")
    rasterizer = native_api.CartoonRasterizer()
    payload = rasterizer.render_rgba(2, 1, [], 0)
    assert isinstance(payload, bytes)
    assert len(payload) == 8
