"""Unit coverage for capacity harness route/AI gates (#191 / PR #241)."""

from __future__ import annotations

from scripts.capacity.concurrent_http_harness import (
    REQUIRED_MIN_SAMPLES,
    ScenarioSummary,
    SharedCallPlanner,
    _evaluate_route_coverage,
    _evaluate_slos,
)


def test_shared_planner_reserves_required_routes_before_round_robin():
    planner = SharedCallPlanner(
        scenario="write-mixed",
        requirements={"ticket_submit": 2, "photo_upload": 1},
    )
    forced = [planner.next()[1] for _ in range(4)]
    assert forced.count("ticket_submit") == 2
    assert forced.count("photo_upload") == 1
    assert forced.count(None) == 1


def test_route_coverage_fails_when_writes_missing():
    by_name = {
        "staff_list": {"count": 4},
        "track_miss": {"count": 4},
        "health_live": {"count": 4},
    }
    coverage = _evaluate_route_coverage("write-mixed", by_name)
    assert coverage["pass"] is False
    assert "ticket_submit" in coverage["missing"]
    assert "photo_upload" in coverage["missing"]
    assert "health_ready_ai" in coverage["missing"]


def test_ai_queue_required_scenario_fails_when_unobserved():
    summary = ScenarioSummary(
        scenario="write-mixed",
        base_url="http://127.0.0.1:9",
        concurrency=1,
        duration_seconds=1,
    )
    by_name = {
        name: {"count": need, "latency_ms": {"p95": 10.0}}
        for name, need in REQUIRED_MIN_SAMPLES["write-mixed"].items()
    }
    slos = _evaluate_slos(summary, by_name)
    assert slos["routeCoverage"]["pass"] is True
    assert slos["aiQueueSamples"]["required"] is True
    assert slos["aiQueueSamples"]["pass"] is False
