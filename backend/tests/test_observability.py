"""Tests for production observability definitions and apply script (issue #185)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.observability.apply_observability import (
    REQUIRED_ALARM_METRICS,
    REQUIRED_DASHBOARD_METRICS,
    main,
    validate_alarms,
    validate_dashboard,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ALARMS_PATH = REPO_ROOT / "infra" / "observability" / "alarms.json"
DASHBOARD_PATH = REPO_ROOT / "infra" / "observability" / "dashboard.json"


def test_checked_in_alarms_cover_acceptance_metrics():
    doc = json.loads(ALARMS_PATH.read_text(encoding="utf-8"))
    assert validate_alarms(doc) == []
    metrics = {alarm["metricName"] for alarm in doc["alarms"]}
    assert REQUIRED_ALARM_METRICS.issubset(metrics)
    for alarm in doc["alarms"]:
        assert alarm["evaluationPeriods"] >= 2
        assert alarm["datapointsToAlarm"] >= 2
        assert "production-observability.md" in alarm["description"]


def test_checked_in_dashboard_covers_service_and_user_flows():
    doc = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    assert validate_dashboard(doc) == []
    metrics: set[str] = set()
    for widget in doc["widgets"]:
        metrics.update(widget.get("metrics") or [])
    assert REQUIRED_DASHBOARD_METRICS.issubset(metrics)


def test_apply_observability_dry_run_succeeds(tmp_path):
    output = tmp_path / "evidence.json"
    code = main(
        [
            "--alarms",
            str(ALARMS_PATH),
            "--dashboard",
            str(DASHBOARD_PATH),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["ok"] is True
    assert evidence["alarmCount"] >= len(REQUIRED_ALARM_METRICS)


def test_apply_requires_alarm_actions(tmp_path):
    output = tmp_path / "evidence.json"
    code = main(
        [
            "--apply",
            "--alarms",
            str(ALARMS_PATH),
            "--dashboard",
            str(DASHBOARD_PATH),
            "--output",
            str(output),
        ]
    )
    assert code == 1
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["ok"] is False
    assert any("alarm-actions" in err for err in evidence["errors"])
