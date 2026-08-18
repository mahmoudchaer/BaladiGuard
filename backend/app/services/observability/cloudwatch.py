"""Least-privilege CloudWatch reads for the developer-operator dashboard."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.core.metrics import NAMESPACE
from app.services.observability.safe import TIME_RANGE_PERIOD, TIME_RANGE_SECONDS

logger = logging.getLogger(__name__)

DASHBOARD_METRICS: tuple[tuple[str, str], ...] = (
    ("HttpRequests", "Sum"),
    ("Http5xx", "Sum"),
    ("HttpRequestDuration", "Average"),
    ("ReadyProbeSuccess", "Minimum"),
    ("AuthFailures", "Sum"),
    ("RateLimitExceeded", "Sum"),
    ("AiQueuePending", "Maximum"),
    ("AiProcessingFailed", "Sum"),
    ("AiJobOldestAgeSeconds", "Maximum"),
    ("S3Errors", "Sum"),
    ("DynamoDbErrors", "Sum"),
    ("NotificationSucceeded", "Sum"),
    ("NotificationFailed", "Sum"),
    ("ImageRedactionJobsDeadLettered", "Sum"),
    ("ReportsSubmitted", "Sum"),
    ("ReportsFailed", "Sum"),
    ("CitizensRegistered", "Sum"),
    ("BackupControlSuccess", "Minimum"),
)

ALARM_NAMES = (
    "BaladiGuard-Sustained5xx",
    "BaladiGuard-ReadinessFailure",
    "BaladiGuard-HighLatency",
    "BaladiGuard-ThrottlingSpike",
    "BaladiGuard-AiQueueBacklog",
    "BaladiGuard-AiProcessingFailures",
    "BaladiGuard-StuckAiJobs",
    "BaladiGuard-RedactionFailures",
    "BaladiGuard-StorageProviderErrors",
    "BaladiGuard-DynamoDbErrors",
    "BaladiGuard-NotificationFailureSpike",
    "BaladiGuard-AuthFailureSpike",
    "BaladiGuard-BackupControlFailure",
    "BaladiGuard-WhatsAppAuthFailure",
    "BaladiGuard-ModerationFailure",
)


class CloudWatchUnavailable(Exception):
    """Raised when CloudWatch cannot be queried; callers must fail over."""


def _client(settings: Settings):
    import boto3

    if not settings.use_dynamodb or settings.dynamodb_endpoint_url:
        raise CloudWatchUnavailable("CloudWatch is not queried against the local/memory backend.")
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "config": Config(
            connect_timeout=2,
            read_timeout=3,
            retries={"max_attempts": 1},
        ),
    }
    try:
        return boto3.client("cloudwatch", **kwargs)
    except Exception as exc:
        raise CloudWatchUnavailable(str(exc)[:160]) from exc


def metric_console_url(*, region: str, metric_name: str, env: str) -> str:
    return (
        f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}"
        f"#metricsV2?graph=~()&namespace={NAMESPACE}&metricName={metric_name}&env={env}"
    )


def alarm_console_url(*, region: str, alarm_name: str) -> str:
    return (
        f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}"
        f"#alarmsV2:alarm/{alarm_name}"
    )


def dashboard_console_url(*, region: str, dashboard_name: str = "BaladiGuard-Production") -> str:
    return (
        f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}"
        f"#dashboards:name={dashboard_name}"
    )


def fetch_metric_data(
    *,
    time_range: str,
    env: str,
    settings: Settings | None = None,
) -> dict[str, list[tuple[datetime, float]]]:
    cfg = settings or get_settings()
    end = datetime.now(UTC)
    start = end - timedelta(seconds=TIME_RANGE_SECONDS[time_range])
    period = TIME_RANGE_PERIOD[time_range]
    queries = []
    for index, (name, stat) in enumerate(DASHBOARD_METRICS):
        queries.append(
            {
                "Id": f"m{index}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": NAMESPACE,
                        "MetricName": name,
                        "Dimensions": [{"Name": "env", "Value": env}],
                    },
                    "Period": period,
                    "Stat": stat,
                },
                "ReturnData": True,
            }
        )
    try:
        client = _client(cfg)
        response = client.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampAscending",
        )
    except CloudWatchUnavailable:
        raise
    except (BotoCoreError, ClientError, Exception) as exc:
        raise CloudWatchUnavailable(str(exc)[:160]) from exc

    id_to_name = {f"m{index}": name for index, (name, _stat) in enumerate(DASHBOARD_METRICS)}
    series: dict[str, list[tuple[datetime, float]]] = {}
    for result in response.get("MetricDataResults") or []:
        metric_name = id_to_name.get(str(result.get("Id") or ""))
        if not metric_name:
            continue
        points = list(zip(result.get("Timestamps") or [], result.get("Values") or [], strict=False))
        series[metric_name] = [
            (stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC), float(value))
            for stamp, value in points
        ]
    return series


def describe_ops_alarms(
    *,
    env: str,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    cfg = settings or get_settings()
    try:
        client = _client(cfg)
        response = client.describe_alarms(AlarmNames=list(ALARM_NAMES))
    except CloudWatchUnavailable:
        raise
    except (BotoCoreError, ClientError, Exception) as exc:
        raise CloudWatchUnavailable(str(exc)[:160]) from exc
    alarms = []
    for alarm in response.get("MetricAlarms") or []:
        dimensions = {item["Name"]: item["Value"] for item in alarm.get("Dimensions") or []}
        if dimensions.get("env") not in {None, env}:
            continue
        alarms.append(alarm)
    return alarms


def backup_control_status(settings: Settings | None = None) -> dict[str, str]:
    cfg = settings or get_settings()
    if not cfg.use_dynamodb:
        return {
            "status": "not_applicable",
            "detail": "Memory backend does not use DynamoDB PITR.",
            "source": "application",
        }
    try:
        import boto3

        kwargs: dict[str, Any] = {"region_name": cfg.aws_region}
        if cfg.dynamodb_endpoint_url:
            kwargs["endpoint_url"] = cfg.dynamodb_endpoint_url
        client = boto3.client("dynamodb", **kwargs)
        table_name = f"{cfg.dynamodb_table_prefix}tickets"
        status = client.describe_continuous_backups(TableName=table_name)
        pitr = (
            status.get("ContinuousBackupsDescription", {})
            .get("PointInTimeRecoveryDescription", {})
            .get("PointInTimeRecoveryStatus")
        )
        if pitr == "ENABLED":
            return {
                "status": "healthy",
                "detail": "Point-in-time recovery is enabled on the tickets table.",
                "source": "aws",
            }
        return {
            "status": "degraded",
            "detail": "Point-in-time recovery is not enabled on the tickets table.",
            "source": "aws",
        }
    except (BotoCoreError, ClientError, Exception) as exc:
        logger.warning("Backup control check failed: %s", type(exc).__name__)
        return {
            "status": "unknown",
            "detail": "Backup control status could not be read.",
            "source": "aws",
        }
