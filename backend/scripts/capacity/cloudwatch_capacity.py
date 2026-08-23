"""Collect deployed capacity signals for #191/#287 evidence.

Safe for evidence: emits aggregates only (no credentials, no PII).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any


def _sum_datapoints(points: list[dict[str, Any]]) -> float:
    total = 0.0
    for point in points:
        if "Sum" in point:
            total += float(point["Sum"])
        elif "SampleCount" in point:
            total += float(point["SampleCount"])
    return total


def collect_capacity_cloudwatch(
    *,
    region: str,
    table_prefix: str,
    s3_bucket: str | None,
    environment: str | None = None,
    ecs_cluster: str | None = None,
    window_minutes: int = 30,
) -> dict[str, Any]:
    """Return application, worker, DynamoDB, and S3 aggregates for the window."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover
        return {"error": f"boto3 unavailable: {exc}"}

    end = datetime.now(UTC)
    start = end - timedelta(minutes=max(5, window_minutes))
    cloudwatch = boto3.client("cloudwatch", region_name=region or "us-east-1")

    ticket_table = f"{table_prefix}tickets"
    metrics: dict[str, Any] = {
        "windowStart": start.isoformat().replace("+00:00", "Z"),
        "windowEnd": end.isoformat().replace("+00:00", "Z"),
        "region": region,
        "ticketTable": ticket_table,
        "s3Bucket": s3_bucket,
        "dynamodb": {},
        "s3": {},
        "application": {},
        "ecs": {},
    }

    dynamo_specs = (
        ("ConsumedWriteCapacityUnits", "Sum"),
        ("ConsumedReadCapacityUnits", "Sum"),
        ("WriteThrottleEvents", "Sum"),
        ("ReadThrottleEvents", "Sum"),
        ("UserErrors", "Sum"),
        ("SystemErrors", "Sum"),
    )
    for metric_name, stat in dynamo_specs:
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/DynamoDB",
                MetricName=metric_name,
                Dimensions=[{"Name": "TableName", "Value": ticket_table}],
                StartTime=start,
                EndTime=end,
                Period=60,
                Statistics=[stat],
            )
            metrics["dynamodb"][metric_name] = {
                "stat": stat,
                "sum": _sum_datapoints(response.get("Datapoints") or []),
                "points": len(response.get("Datapoints") or []),
            }
        except Exception as exc:  # noqa: BLE001 - evidence helper boundary
            metrics["dynamodb"][metric_name] = {"error": type(exc).__name__}

    if s3_bucket:
        for metric_name in ("5xxErrors", "4xxErrors", "AllRequests"):
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace="AWS/S3",
                    MetricName=metric_name,
                    Dimensions=[
                        {"Name": "BucketName", "Value": s3_bucket},
                        {"Name": "FilterId", "Value": "EntireBucket"},
                    ],
                    StartTime=start,
                    EndTime=end,
                    Period=60,
                    Statistics=["Sum"],
                )
                metrics["s3"][metric_name] = {
                    "sum": _sum_datapoints(response.get("Datapoints") or []),
                    "points": len(response.get("Datapoints") or []),
                }
            except Exception as exc:  # noqa: BLE001
                metrics["s3"][metric_name] = {"error": type(exc).__name__}

    if environment:
        application_specs = (
            ("HttpRequests", "Sum"),
            ("HttpRequestDuration", "Average"),
            ("HttpRequestDuration", "p95"),
            ("Http5xx", "Sum"),
            ("ReportsSubmitted", "Sum"),
            ("AiJobsQueued", "Sum"),
            ("AiJobsSucceeded", "Sum"),
            ("AiJobsRetried", "Sum"),
            ("AiJobsDeadLettered", "Sum"),
            ("AiJobOldestAgeSeconds", "Maximum"),
            ("AiQueuePending", "Maximum"),
            ("S3Errors", "Sum"),
        )
        for metric_name, stat in application_specs:
            key = metric_name if stat != "p95" else f"{metric_name}P95"
            kwargs: dict[str, Any] = {
                "Namespace": "BaladiGuard",
                "MetricName": metric_name,
                "Dimensions": [{"Name": "env", "Value": environment}],
                "StartTime": start,
                "EndTime": end,
                "Period": 60,
            }
            if stat == "p95":
                kwargs["ExtendedStatistics"] = [stat]
            else:
                kwargs["Statistics"] = [stat]
            try:
                response = cloudwatch.get_metric_statistics(**kwargs)
                points = response.get("Datapoints") or []
                values = [
                    float(point.get(stat, point.get("ExtendedStatistics", {}).get(stat, 0)))
                    for point in points
                ]
                metrics["application"][key] = {
                    "stat": stat,
                    "value": sum(values) if stat == "Sum" else (max(values) if values else None),
                    "points": len(points),
                }
            except Exception as exc:  # noqa: BLE001
                metrics["application"][key] = {"error": type(exc).__name__}

    if ecs_cluster:
        for service in ("api", "ai-worker", "redaction-worker"):
            service_name = f"{ecs_cluster}-{service}"
            metrics["ecs"][service] = {}
            for metric_name, stat in (
                ("RunningTaskCount", "Minimum"),
                ("CpuUtilized", "Average"),
                ("MemoryUtilized", "Average"),
            ):
                try:
                    response = cloudwatch.get_metric_statistics(
                        Namespace="ECS/ContainerInsights",
                        MetricName=metric_name,
                        Dimensions=[
                            {"Name": "ClusterName", "Value": ecs_cluster},
                            {"Name": "ServiceName", "Value": service_name},
                        ],
                        StartTime=start,
                        EndTime=end,
                        Period=60,
                        Statistics=[stat],
                    )
                    points = response.get("Datapoints") or []
                    values = [float(point[stat]) for point in points if stat in point]
                    metrics["ecs"][service][metric_name] = {
                        "stat": stat,
                        "value": min(values)
                        if stat == "Minimum" and values
                        else (max(values) if values else None),
                        "points": len(points),
                    }
                except Exception as exc:  # noqa: BLE001
                    metrics["ecs"][service][metric_name] = {"error": type(exc).__name__}

    return metrics


def load_dotenv_into(env: dict[str, str]) -> None:
    """Merge backend/.env and repo /.env into env without printing values."""
    from pathlib import Path

    from dotenv import dotenv_values

    backend = Path(__file__).resolve().parents[2]
    repo = backend.parent
    for path in (backend / ".env", repo / ".env"):
        if not path.exists():
            continue
        for key, value in dotenv_values(path).items():
            if value is None:
                continue
            env.setdefault(key, value)


def cloud_mode_requested() -> bool:
    flag = (os.environ.get("CAPACITY_CLOUD") or "").strip().lower()
    return flag in {"1", "true", "yes", "on", "cloud", "dynamodb"}
