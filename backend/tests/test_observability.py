"""Tests for production observability definitions and apply script (issue #185)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.metrics import STABLE_EMF_DIMENSION_KEYS, build_emf_record
from scripts.observability.apply_observability import (
    REQUIRED_ALARM_METRICS,
    REQUIRED_DASHBOARD_METRICS,
    STABLE_DIMENSION_KEYS,
    build_alarm_put_kwargs,
    build_dashboard_body,
    main,
    validate_alarms,
    validate_dashboard,
)
from scripts.observability.staging_drill import main as staging_drill_main

REPO_ROOT = Path(__file__).resolve().parents[2]
ALARMS_PATH = REPO_ROOT / "infra" / "observability" / "alarms.json"
DASHBOARD_PATH = REPO_ROOT / "infra" / "observability" / "dashboard.json"


def test_checked_in_alarms_cover_acceptance_metrics():
    doc = json.loads(ALARMS_PATH.read_text(encoding="utf-8"))
    assert validate_alarms(doc) == []
    metrics = {alarm["metricName"] for alarm in doc["alarms"]}
    assert REQUIRED_ALARM_METRICS.issubset(metrics)
    assert tuple(doc["dimensionKeys"]) == STABLE_DIMENSION_KEYS
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


def test_emf_and_alarm_dimension_sets_match():
    assert STABLE_DIMENSION_KEYS == STABLE_EMF_DIMENSION_KEYS
    emf = build_emf_record("ReadyProbeSuccess", value=1.0, unit="None", env="staging")
    assert emf["_aws"]["CloudWatchMetrics"][0]["Dimensions"] == [list(STABLE_EMF_DIMENSION_KEYS)]
    assert emf["env"] == "staging"
    assert "version" not in emf


def test_put_metric_alarm_payload_selects_env_dimension():
    alarms = json.loads(ALARMS_PATH.read_text(encoding="utf-8"))
    kwargs = build_alarm_put_kwargs(
        alarms["alarms"][0],
        namespace="BaladiGuard",
        env="staging",
        alarm_actions=["arn:aws:sns:us-east-1:123:ops"],
    )
    assert kwargs["Dimensions"] == [{"Name": "env", "Value": "staging"}]
    assert kwargs["Namespace"] == "BaladiGuard"
    assert "version" not in {dim["Name"] for dim in kwargs["Dimensions"]}


def test_dashboard_body_queries_include_env_dimension():
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    body = build_dashboard_body(
        dashboard,
        namespace="BaladiGuard",
        env="staging",
        region="us-east-1",
    )
    metric_widgets = [w for w in body["widgets"] if w["type"] == "metric"]
    assert metric_widgets
    for widget in metric_widgets:
        for series in widget["properties"]["metrics"]:
            assert series[0] == "BaladiGuard"
            assert "env" in series
            assert "staging" in series
            assert "version" not in series


def test_apply_observability_dry_run_succeeds(tmp_path):
    output = tmp_path / "evidence.json"
    code = main(
        [
            "--alarms",
            str(ALARMS_PATH),
            "--dashboard",
            str(DASHBOARD_PATH),
            "--env",
            "staging",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["ok"] is True
    assert evidence["env"] == "staging"
    assert evidence["alarmCount"] >= len(REQUIRED_ALARM_METRICS)
    assert all(
        payload["Dimensions"] == [{"Name": "env", "Value": "staging"}]
        for payload in evidence["previewAlarmPayloads"]
    )


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


def test_staging_drill_simulated_ok_and_alarm_transitions(tmp_path):
    output = tmp_path / "drill.json"
    code = staging_drill_main(
        [
            "--env",
            "staging",
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
    assert evidence["mode"] == "simulated"
    assert evidence["transitions"] == {
        "healthy": "OK",
        "failure": "ALARM",
        "restored": "OK",
    }
    assert evidence["readinessAlarmPayload"]["Dimensions"] == [{"Name": "env", "Value": "staging"}]
