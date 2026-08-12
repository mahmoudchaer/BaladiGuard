"""Collect CloudWatch capacity signals for #191 evidence (DynamoDB / S3).

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
    window_minutes: int = 30,
) -> dict[str, Any]:
    """Return DynamoDB throttle/capacity and S3 error aggregates for the window."""
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
