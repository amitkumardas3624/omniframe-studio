"""Task 3: Verification levels bound to bridge fixtures.

Every bridge ships generation/structural tests that must carry an *honest*
verification level. On this machine none of the proprietary host applications
(Premiere Pro / After Effects / DaVinci Resolve / CapCut / Krita) is installed,
so a bridge test can honestly claim at most ``structurally_checked``. It must
NEVER claim ``render_tested`` or ``production_candidate``: producing frames on
screen (or a hand-offs-ready deliverable) requires opening and executing inside
the real host application, which is an operator step.

The verification vocabulary reuses Phase 1's contract (also used by
``omniframe.engines.code_video.renderer.RenderResult.verification_level``):

    generated | structurally_checked | import_tested | render_tested | production_candidate

This module is deliberately self-contained: it reads only the already-shipped
public bridge surface (``get_bridge`` / ``list_bridges`` / ``BRIDGES``) and never
depends on files that parallel workers may be mid-edit (fixtures, loss module).
No host is launched; there are no ffmpeg or network dependencies.
"""

from __future__ import annotations

import pytest

from omniframe.bridges import BRIDGES, BridgeTier, get_bridge, list_bridges

#: The full verification vocabulary inherited from Phase 1 (renderer.py).
VERIFICATION_LEVELS: frozenset[str] = frozenset(
    {
        "generated",
        "structurally_checked",
        "import_tested",
        "render_tested",
        "production_candidate",
    }
)

#: Levels a bridge test can honestly claim WITHOUT opening a real host.
#: ``import_tested`` would require importing the generated artifact into the
#: host, so it is excluded here.
HOST_FREE_LEVELS: frozenset[str] = frozenset({"generated", "structurally_checked"})

#: Single source of truth: the verification level each bridge's fixture tests
#: are allowed to claim, plus an honest reason.  Nothing here may reach
#: ``render_tested`` / ``production_candidate`` while the host is absent.
BRIDGE_LEVELS: dict[str, str] = {
    "premiere_pro": "structurally_checked",
    "after_effects": "structurally_checked",
    "davinci_resolve": "structurally_checked",
    "capcut": "structurally_checked",
    "krita": "structurally_checked",
}

BRIDGE_LEVEL_REASONS: dict[str, str] = {
    "premiere_pro": (
        "Generated .jsx + FCPXML sidecar are parsed/structure-checked; ExtendScript "
        "was never executed inside Premiere Pro (host absent)."
    ),
    "after_effects": (
        "Generated .jsx adds comps via the documented DOM and is structure-checked; "
        "AE was never opened."
    ),
    "davinci_resolve": (
        "Generated script references the documented DaVinciResolveScript API and the "
        "XML sidecar is structure-checked; Resolve was never opened."
    ),
    "capcut": (
        "Generated draft is validated as JSON (materials/tracks present); CapCut was "
        "never opened."
    ),
    "krita": (
        "Generated document/frame metadata is structure-checked; Krita was never opened."
    ),
}


class TestHonestyBoundary:
    """The hard honesty boundary: never claim a host-only verification level."""

    def test_no_bridge_is_render_tested_or_production_candidate(self):
        assert all(
            level in HOST_FREE_LEVELS for level in BRIDGE_LEVELS.values()
        ), (
            "A bridge fixture claimed a host-only verification level "
            f"(got {BRIDGE_LEVELS.values()!r}). Without an installed host you may "
            "only claim 'generated' or 'structurally_checked'."
        )

    def test_level_vocabulary_matches_phase1_contract(self):
        # Every assigned level is one of the documented Phase 1 vocabulary values.
        assert set(BRIDGE_LEVELS.values()).issubset(VERIFICATION_LEVELS)
        assert set(BRIDGE_LEVELS.values()).issubset(HOST_FREE_LEVELS)

    def test_source_of_truth_covers_every_registered_bridge(self):
        # Keep the mapping in sync with the registry; any new bridge must be
        # assigned an honest verification level here.
        assert set(BRIDGE_LEVELS) == set(BRIDGES)
        assert set(BRIDGE_LEVEL_REASONS) == set(BRIDGES)


class TestBridgeDetectionState:
    """Every bridge answers detect() honestly, with capability tiers in range."""

    def test_detect_each_bridge_within_bridgetier(self):
        """detect() never raises and every capability tier is a valid BridgeTier."""
        for bridge_id in sorted(BRIDGES):
            report = get_bridge(bridge_id).detect()
            assert report.bridge == bridge_id
            assert isinstance(report.installed, bool)
            assert report.capabilities, f"{bridge_id} reported no capabilities"
            for capability in report.capabilities:
                assert capability.tier in set(BridgeTier), (
                    f"{bridge_id} capability '{capability.name}' has an invalid tier "
                    f"{capability.tier!r}"
                )

    def test_all_hosts_absent_is_the_expected_state_here(self):
        """Lock the honesty contract for this machine: no host is installed.

        If a host were installed later, this assertion would fail loudly instead of
        silently letting a bridge test claim more than it ran — a deliberate safety
        tripwire.  ``installed`` is still asserted to be a real bool for every bridge.
        """
        reports = [get_bridge(bridge_id).detect() for bridge_id in set(BRIDGES)]
        assert all(isinstance(report.installed, bool) for report in reports)
        installed = {report.bridge for report in reports if report.installed}
        assert not installed, (
            "Expected no host on this machine, but found installed: "
            f"{sorted(installed)}. Re-verify before claiming render_tested."
        )

    def test_list_bridges_reports_installed_bool(self):
        for entry in list_bridges():
            assert entry["id"] in BRIDGE_LEVELS
            assert isinstance(entry["installed"], bool)


@pytest.mark.bridge_host
def test_real_host_launch_is_an_operator_step():
    """Demonstrates the ``bridge_host`` marker.

    Any test that opens a real proprietary host must be marked ``bridge_host``.
    On this machine no host is installed, so the test is skipped (with a reason)
    rather than failed — proving the marker's skip path is wired up.
    """
    installed = sorted(
        bridge_id for bridge_id in BRIDGES if get_bridge(bridge_id).detect().installed
    )
    if not installed:
        pytest.skip(
            "No proprietary host application is installed on this machine; "
            "running a host is a human/operator step. Skipped rather than failed."
        )
    # Reached only when a real host exists: document that launching it and
    # capturing a real render is the responsibility of the operator, and that
    # this test alone is insufficient evidence of 'render_tested'.
    raise AssertionError(
        "A bridge_host test that reaches this branch must actually drive the "
        f"installed host ({installed}) and record evidence; it was not executed."
    )


class TestBridgeHostMarkingConvention:
    """The marking convention is enforced by the registered marker."""

    def test_bridge_host_marker_is_registered_in_config(self, pytestconfig):
        raw_markers = pytestconfig.getini("markers")
        names: set[str] = set()
        for item in raw_markers:
            name = getattr(item, "name", None)
            if name is not None:
                names.add(str(name))
            else:
                names.add(str(item).split(":", 1)[0].strip())
        assert "bridge_host" in names, (
            "The 'bridge_host' marker must be registered in pyproject.toml "
            "[tool.pytest.ini_options] markers, or --strict-markers rejects any "
            "test that uses it."
        )