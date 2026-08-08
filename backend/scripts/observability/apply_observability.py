"""Validate and apply CloudWatch dashboards/alarms for BaladiGuard (issue #185).

Default mode is dry-run validation of checked-in JSON. ``--apply`` requires AWS
credentials and creates/updates the dashboard and metric alarms. Thresholds are
intentionally multi-period so a single expected failure does not page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ALARMS = REPO_ROOT / "infra" / "observability" / "alarms.json"
DEFAULT_DASHBOARD = REPO_ROOT / "infra" / "observability" / "dashboard.json"

REQUIRED_ALARM_METRICS = {
    "Http5xx",
    "ReadyProbeSuccess",
    "AiQueuePending",
    "AiProcessingFailed",
    "S3Errors",
    "DynamoDbErrors",
    "NotificationFailed",
}

REQUIRED_DASHBOARD_METRICS = {
    "HttpRequests",
    "Http5xx",
    "HttpRequestDuration",
    "ReadyProbeSuccess",
    "AuthFailures",
    "RateLimitExceeded",
    "AiQueuePending",
    "AiProcessingFailed",
    "S3Errors",
    "DynamoDbErrors",
    "NotificationSucceeded",
    "NotificationFailed",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_alarms(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if doc.get("namespace") != "BaladiGuard":
        errors.append("alarms.namespace must be BaladiGuard")
    if not doc.get("runbookUrl"):
        errors.append("alarms.runbookUrl is required")
    alarms = doc.get("alarms")
    if not isinstance(alarms, list) or not alarms:
        errors.append("alarms.alarms must be a non-empty list")
        return errors

    names: set[str] = set()
    metrics: set[str] = set()
    for alarm in alarms:
        name = alarm.get("alarmName")
        metric = alarm.get("metricName")
        if not name or not metric:
            errors.append("each alarm needs alarmName and metricName")
            continue
        if name in names:
            errors.append(f"duplicate alarmName: {name}")
        names.add(name)
        metrics.add(metric)
        if int(alarm.get("evaluationPeriods", 0)) < 2:
            errors.append(f"{name}: evaluationPeriods must be >= 2 to avoid single-blip pages")
        if int(alarm.get("datapointsToAlarm", 0)) < 2:
            errors.append(f"{name}: datapointsToAlarm must be >= 2")
        description = str(alarm.get("description") or "")
        if "production-observability.md" not in description:
            errors.append(f"{name}: description must link the observability runbook")
        if alarm.get("treatMissingData") not in {"notBreaching", "breaching", "ignore"}:
            errors.append(f"{name}: invalid treatMissingData")
    missing = REQUIRED_ALARM_METRICS - metrics
    if missing:
        errors.append(f"missing required alarm metrics: {sorted(missing)}")
    return errors


def validate_dashboard(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not doc.get("dashboardName"):
        errors.append("dashboard.dashboardName is required")
    widgets = doc.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        errors.append("dashboard.widgets must be a non-empty list")
        return errors
    metrics: set[str] = set()
    for widget in widgets:
        for metric in widget.get("metrics") or []:
            metrics.add(metric)
    missing = REQUIRED_DASHBOARD_METRICS - metrics
    if missing:
        errors.append(f"dashboard missing metrics: {sorted(missing)}")
    return errors


def _cloudwatch_client(region: str):
    import boto3

    return boto3.client("cloudwatch", region_name=region)


def apply_dashboard(client, doc: dict[str, Any], namespace: str) -> None:
    widgets = []
    x = 0
    y = 0
    for index, widget in enumerate(doc["widgets"]):
        width = 12
        height = 6
        if widget.get("type") == "text":
            body = {
                "type": "text",
                "x": x,
                "y": y,
                "width": 24,
                "height": 3,
                "properties": {
                    "markdown": f"## {widget.get('title', 'Notes')}\n\n{widget.get('markdown', '')}"
                },
            }
            widgets.append(body)
            y += 3
            x = 0
            continue
        metrics = []
        for metric_name in widget.get("metrics") or []:
            metrics.append([namespace, metric_name])
        body = {
            "type": "metric",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "properties": {
                "title": widget.get("title") or f"Widget {index}",
                "view": "timeSeries",
                "stacked": False,
                "region": client.meta.region_name,
                "stat": widget.get("stat") or "Sum",
                "period": int(widget.get("periodSeconds") or 60),
                "metrics": metrics,
            },
        }
        widgets.append(body)
        x += width
        if x >= 24:
            x = 0
            y += height
    client.put_dashboard(
        DashboardName=doc["dashboardName"],
        DashboardBody=json.dumps({"widgets": widgets}),
    )


def apply_alarms(
    client,
    doc: dict[str, Any],
    *,
    alarm_actions: list[str],
) -> list[str]:
    applied: list[str] = []
    namespace = doc["namespace"]
    for alarm in doc["alarms"]:
        kwargs: dict[str, Any] = {
            "AlarmName": alarm["alarmName"],
            "AlarmDescription": alarm.get("description") or "",
            "Namespace": namespace,
            "MetricName": alarm["metricName"],
            "Statistic": alarm.get("statistic") or "Sum",
            "Period": int(alarm["periodSeconds"]),
            "EvaluationPeriods": int(alarm["evaluationPeriods"]),
            "DatapointsToAlarm": int(alarm["datapointsToAlarm"]),
            "Threshold": float(alarm["threshold"]),
            "ComparisonOperator": alarm["comparisonOperator"],
            "TreatMissingData": alarm.get("treatMissingData") or "notBreaching",
            "ActionsEnabled": bool(alarm_actions),
        }
        if alarm_actions:
            kwargs["AlarmActions"] = alarm_actions
            kwargs["OKActions"] = alarm_actions
        client.put_metric_alarm(**kwargs)
        applied.append(alarm["alarmName"])
    return applied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alarms", type=Path, default=DEFAULT_ALARMS)
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create/update CloudWatch dashboard and alarms (requires AWS creds).",
    )
    parser.add_argument(
        "--alarm-actions",
        default=os.getenv("OBSERVABILITY_ALARM_ACTIONS", ""),
        help="Comma-separated SNS ARNs for alarm notifications.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region for CloudWatch APIs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON evidence path for dry-run/apply results.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    alarms_doc = load_json(args.alarms)
    dashboard_doc = load_json(args.dashboard)
    errors = validate_alarms(alarms_doc) + validate_dashboard(dashboard_doc)
    result: dict[str, Any] = {
        "ok": not errors,
        "errors": errors,
        "alarmsPath": str(args.alarms),
        "dashboardPath": str(args.dashboard),
        "apply": bool(args.apply),
        "alarmCount": len(alarms_doc.get("alarms") or []),
        "widgetCount": len(dashboard_doc.get("widgets") or []),
        "appliedAlarms": [],
    }
    if errors:
        print(json.dumps(result, indent=2))
        if args.output:
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1

    if args.apply:
        actions = [item.strip() for item in args.alarm_actions.split(",") if item.strip()]
        if not actions:
            result["ok"] = False
            result["errors"] = [
                "--apply requires --alarm-actions or OBSERVABILITY_ALARM_ACTIONS "
                "(SNS topic ARN) so alerts reach the team."
            ]
            print(json.dumps(result, indent=2))
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return 1
        client = _cloudwatch_client(args.region)
        apply_dashboard(client, dashboard_doc, alarms_doc["namespace"])
        result["appliedAlarms"] = apply_alarms(client, alarms_doc, alarm_actions=actions)
        result["dashboardName"] = dashboard_doc["dashboardName"]

    print(json.dumps(result, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
