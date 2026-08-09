"""Tests for production observability definitions and apply script (issue #185)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
from scripts.observability.staging_drill import (
    clean_recovery_sample_times,
    completed_period_sample_times,
)
from scripts.observability.staging_drill import (
    main as staging_drill_main,
)

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


def test_staging_drill_separates_organic_evaluation_and_sns_delivery(tmp_path):
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
    assert evidence["organicEvaluation"]["healthyVerdict"] == "OK"
    assert evidence["organicEvaluation"]["failureVerdict"] == "ALARM"
    assert evidence["organicEvaluation"]["recoveryVerdict"] == "OK"
    assert evidence["organicEvaluation"]["recoveryVerified"] is True
    assert evidence["alarmPolicyMatchesCheckedIn"] is True
    assert evidence["appliedAlarmPolicy"] == evidence["checkedInAlarmPolicy"]
    assert evidence["appliedAlarmPolicy"] == {
        "metricName": "ReadyProbeSuccess",
        "statistic": "Minimum",
        "periodSeconds": 60,
        "evaluationPeriods": 3,
        "datapointsToAlarm": 3,
        "threshold": 1.0,
        "comparisonOperator": "LessThanThreshold",
        "treatMissingData": "breaching",
        "dimensions": [{"Name": "env", "Value": "staging"}],
    }
    assert evidence["snsDelivery"]["deliveryConfirmed"] is True
    states = {
        item.get("newStateValue")
        for item in (
            evidence["snsDelivery"]["alarmNotifications"]
            + evidence["snsDelivery"]["okNotifications"]
        )
    }
    assert "ALARM" in states
    assert "OK" in states
    assert evidence["readinessAlarmPayload"]["Dimensions"] == [{"Name": "env", "Value": "staging"}]


def test_organic_ready_verdict_helper():
    from scripts.observability.staging_drill import organic_ready_verdict

    assert organic_ready_verdict([1.0, 1.0, 1.0]) == "OK"
    assert organic_ready_verdict([0.0, 0.0, 0.0]) == "ALARM"
    assert organic_ready_verdict([1.0, 0.0]) == "INSUFFICIENT_DATA"


def test_staging_evidence_masks_aws_account_ids():
    from scripts.observability.staging_drill import mask_account_ids, sanitize_notification

    arn = "arn:aws:sns:us-east-1:123456789012:baladiguard-staging-alerts"
    assert mask_account_ids({"AlarmActions": [arn]}) == {
        "AlarmActions": ["arn:aws:sns:us-east-1:****:baladiguard-staging-alerts"]
    }
    notice = sanitize_notification(
        {
            "Subject": f"Successfully executed action {arn}",
            "AlarmName": "BaladiGuard-ReadinessFailure",
        }
    )
    assert "123456789012" not in notice["subject"]


def test_recovery_samples_are_scheduled_in_subsequent_clean_periods():
    now = datetime(2026, 8, 9, 12, 34, 40, tzinfo=UTC)
    failures = completed_period_sample_times(3, period_seconds=60, now=now)
    recovery = clean_recovery_sample_times(3, period_seconds=60, now=now)

    assert [item.isoformat() for item in failures] == [
        "2026-08-09T12:31:05+00:00",
        "2026-08-09T12:32:05+00:00",
        "2026-08-09T12:33:05+00:00",
    ]
    assert [item.isoformat() for item in recovery] == [
        "2026-08-09T12:35:05+00:00",
        "2026-08-09T12:36:05+00:00",
        "2026-08-09T12:37:05+00:00",
    ]
    assert min(recovery) > max(failures)


def test_live_drill_rejects_a_wait_shorter_than_checked_in_policy():
    code = staging_drill_main(
        [
            "--live",
            "--env",
            "staging",
            "--alarm-actions",
            "arn:aws:sns:us-east-1:123456789012:ops",
            "--organic-wait-seconds",
            "179",
        ]
    )
    assert code == 1
