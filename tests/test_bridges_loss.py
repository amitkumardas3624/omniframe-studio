"""Tests for bridge translation/inspection loss reporting.

Covers the pure :mod:`omniframe.bridges.loss` module and the additive
``"loss"`` key that the default ``ToolBridge.inspect()`` emits when its
recursive directory walk hits the 500-entry cap.
"""

from __future__ import annotations

import json

from omniframe.bridges.base import ToolBridge
from omniframe.bridges.loss import LossItem, LossReport, record_loss


def test_binary_loss_report_is_json_serialisable():
    report = record_loss(
        "capcut",
        [
            LossItem("markers", "supported"),
            LossItem("keyframes", "unsupported", reason="undocumented format"),
        ],
    )
    decoded = json.loads(json.dumps(report.to_dict()))
    assert decoded["bridge"] == "capcut"
    assert isinstance(decoded["total"], int)
    assert len(decoded["items"]) == 2
    assert decoded["items"][0]["feature"] == "markers"
    assert decoded["items"][0]["status"] == "supported"
    assert decoded["items"][1]["reason"] == "undocumented format"


def test_summary_counts_by_status():
    report = LossReport(
        bridge="premiere_pro",
        total=4,
        items=[
            LossItem("a", "supported"),
            LossItem("b", "supported"),
            LossItem("c", "degraded", reason="legacy field"),
            LossItem("d", "unsupported"),
        ],
    )
    assert report.summary() == {"supported": 2, "degraded": 1, "unsupported": 1}


def test_record_loss_sets_total_to_item_count():
    items = [
        LossItem("x", "supported"),
        LossItem("y", "degraded"),
        LossItem("z", "unsupported"),
    ]
    report = record_loss("after_effects", items)
    assert isinstance(report, LossReport)
    assert report.total == len(items) == 3
    assert report.bridge == "after_effects"


class _DefaultInspectBridge(ToolBridge):
    """A thin bridge that keeps the default ``ToolBridge.inspect()``."""

    id = "default_inspect_bridge"
    host = "Default Inspect Host"

    def detect(self):
        from omniframe.bridges.base import BridgeReport

        return BridgeReport(bridge=self.id, host=self.host, installed=False)

    def capabilities(self):
        return []


def test_inspect_directory_over_500_entries_reports_loss(tmp_path):
    for i in range(520):
        (tmp_path / f"file_{i:04d}.bin").write_bytes(b"placeholder")
    report = _DefaultInspectBridge().inspect(tmp_path)
    assert report.get("exists") is True
    assert report.get("truncated") is True
    loss = report.get("loss")
    assert loss is not None
    assert loss["bridge"] == "default_inspect_bridge"
    assert loss["total"] == 1
    assert loss["summary"].get("degraded", 0) >= 1
    assert loss["items"][0]["status"] == "degraded"
    assert "truncated" in loss["items"][0]["reason"]


def test_inspect_normal_directory_has_no_loss_key(tmp_path):
    for i in range(3):
        (tmp_path / f"file_{i}.bin").write_bytes(b"data")
    report = _DefaultInspectBridge().inspect(tmp_path)
    assert report.get("exists") is True
    assert "truncated" not in report
    assert "loss" not in report