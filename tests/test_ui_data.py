"""Host-independent JSON contract checks for ``GET /api/v1/tools``.

These tests verify that the /api/v1/tools endpoint the UI consumes returns
the same manifest the runtime registry produces. They only exercise the
in-process FastAPI app, so they never depend on an external host/browser.

When FastAPI is not installed the whole module is skipped (not failed) via
``pytest.importorskip``.
"""

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841  (skips module if missing)

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402
from omniframe.core.agent_runtime.actions import ensure_builtin_actions  # noqa: E402


def _tools_response():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/tools")

    assert response.status_code == 200, response.text
    return response.json()


def test_tools_endpoint_matches_runtime_manifest() -> None:
    """The endpoint's tools list equals the runtime manifest's tool list.

    The route returns ``ActionOutput.success/result`` where
    ``result == {"tools": registry.to_tool_schemas(), "count": ...}``.
    ``to_json_document()`` wraps the same ``to_tool_schemas()`` list, so the
    reconciled contract is ``payload.result.tools == manifest["tools"]``.
    """
    registry = ensure_builtin_actions()
    manifest = registry.to_json_document()

    payload = _tools_response()

    assert payload["success"] is True
    result = payload["result"]
    assert isinstance(result["tools"], list)
    # Endpoint contract shape: tools + count (not the full manifest document).
    assert result["tools"] == manifest["tools"]
    assert result["tools"] == registry.to_tool_schemas()
    assert result["count"] == len(registry.names())
    assert result["count"] == len(result["tools"])


def test_tools_endpoint_tools_are_named_and_described() -> None:
    """Each tool entry is complete enough to drive the UI Actions panel."""
    payload = _tools_response()
    tools = payload["result"]["tools"]

    assert tools, "expected at least one registered tool"
    for tool in tools:
        assert tool.get("name"), "each tool must carry a name"
        assert "description" in tool, "each tool must carry a description"
        assert "inputSchema" in tool, "each tool must carry an input schema"