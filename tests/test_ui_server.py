"""Host-independent checks for the backend app itself.

When FastAPI is not installed the whole module is skipped (not failed) via
``pytest.importorskip``, matching the other UI test modules.
"""

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841  (skips module if missing)

from fastapi.testclient import TestClient  # noqa: E402

from omniframe.backend.server import create_app  # noqa: E402


def test_ui_app_starts_and_serves_health() -> None:
    for _ in range(2):
        with TestClient(create_app()) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_ui_serves_real_interface_instead_of_placeholder() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/ui")

    assert response.status_code == 200
    assert "<title>OmniFrame Studio — Agent & Creator Control Panel</title>" in response.text
    assert "Web UI not yet built" not in response.text
    assert "Update Available" in response.text
    assert "/api/v1/system/update-status" in response.text
    assert "/api/v1/system/update" in response.text
    assert "/api/v1/system/restart" in response.text
    assert "/api/v1/tools" in response.text
    assert "loadTools" in response.text
    assert "runDoctor" in response.text
    assert "renderDashboard" in response.text
    assert "fallbackHealthPoll" in response.text


def test_tools_endpoint_returns_registered_actions() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/tools")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["result"]["tools"]) == 19
    assert payload["result"]["tools"][0]["name"]


def test_environment_endpoint_is_gettable_by_ui() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/environment")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "python" in response.json()["result"]["output"].lower()


def test_agent_activity_websocket_accepts_same_origin_connection() -> None:
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/agent-activity") as websocket:
            websocket.send_text("ping")
