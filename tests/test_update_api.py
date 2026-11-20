from __future__ import annotations

import json

from fastapi.testclient import TestClient

import omniframe.backend.server as server


def test_update_status_returns_mocked_update(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "check_for_update",
        lambda **_: {
            "current_version": "0.1.0",
            "latest_version": "0.2.0",
            "update_available": True,
            "release_url": "https://example.test/release",
        },
    )

    with TestClient(server.create_app()) as client:
        response = client.get("/api/v1/system/update-status")

    assert response.status_code == 200
    assert response.json()["result"]["update_available"] is True


def test_update_stream_and_restart_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "stream_update_events",
        lambda: iter([{"event": "completed", "success": True}]),
    )

    with TestClient(server.create_app()) as client:
        stream = client.post("/api/v1/system/update")
        restart = client.post("/api/v1/system/restart")

    assert json.loads(stream.text.splitlines()[-1])["event"] == "completed"
    assert restart.json()["result"]["restart_required"] is True


def test_action_output_contains_cached_update_advisory(monkeypatch) -> None:
    monkeypatch.setattr(
        server,
        "get_cached_update_advisory",
        lambda: {"latest_version": "0.2.0", "release_url": "https://example.test/release"},
    )

    output = server.ActionOutput(success=True, result={"ok": True})

    assert output.update_available is True
    assert output.update_info["latest_version"] == "0.2.0"
