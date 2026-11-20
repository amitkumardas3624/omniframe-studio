from __future__ import annotations


def test_native_status_is_nonfatal_without_extension():
    from omniframe._native import native_status

    status = native_status()
    assert status["mode"] in {"native", "fallback"}
    assert "available" in status
    assert "backend" in status


def test_fallback_frame_sink_writes_rgba_png(tmp_path):
    from omniframe._native.fallback import FramePipeSink

    sink = FramePipeSink(output_dir=tmp_path, fps=24, width=2, height=1)
    sink.write_rgba(bytes([255, 0, 0, 255, 0, 255, 0, 255]), 2, 1)
    sink.close()
    frames = list(tmp_path.glob("frame_*.png"))
    assert [path.name for path in frames] == ["frame_000000.png"]


def test_native_request_fails_actionably_when_unavailable(tmp_path):
    from omniframe._native import native_available, get_frame_sink
    from omniframe.core.errors import EngineUnavailable

    if native_available():
        return
    try:
        get_frame_sink(tmp_path, fps=24, width=2, height=1, backend="native")
    except EngineUnavailable as exc:
        assert exc.code == "E_ENGINE_UNAVAILABLE"
        assert exc.details["capability"] == "native_accelerator"
    else:  # pragma: no cover - protects the contract if the loader changes
        raise AssertionError("backend='native' should fail without the extension")
