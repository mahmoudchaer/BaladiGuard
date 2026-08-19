"""Developer-operator dashboard assembly (issue #320)."""

from __future__ import annotations

import logging
import os
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import redact_text
from app.core.metrics import recent_metric_samples
from app.core.staff_auth import StaffPrincipal
from app.database.store_factory import (
    get_ai_job_store,
    get_notification_delivery_store,
    get_ops_alert_ack_store,
    get_ops_audit_store,
    get_ops_error_store,
    get_redaction_job_store,
    get_ticket_store,
)
from app.schemas.ops import (
    AlertRecord,
    BackupStatus,
    ErrorGroup,
    HealthSummary,
    NamedMetricSeries,
    OpsMetricsResponse,
    OpsOverviewResponse,
    ProductMetrics,
    ReplayJobResponse,
    SafeJobRow,
    WorkerQueueSummary,
)
from app.schemas.stored_ops import StoredOpsAlertAck, StoredOpsAudit
from app.services.health import build_health_payload, build_readiness_payload
from app.services.observability.cloudwatch import (
    ALARM_NAMES,
    CloudWatchUnavailable,
    alarm_console_url,
    backup_control_status,
    dashboard_console_url,
    describe_ops_alarms,
    fetch_metric_data,
)
from app.services.observability.runbooks import all_runbooks, runbook_for
from app.services.observability.safe import (
    TIME_RANGE_SECONDS,
    hash_identifier,
    is_safe_alarm_name,
    is_safe_job_id,
    sanitize_ops_text,
)

logger = logging.getLogger(__name__)

MUNICIPALITY_NAV = {
    "available": False,
    "issue": "322",
    "label": "Municipality management is owned by the multi-municipality control-plane issue.",
}

OPEN_TICKET_STATUSES = {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"}


def _iso(moment: datetime | None = None) -> str:
    value = moment or datetime.now(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _env(settings: Settings) -> str:
    return (
        os.getenv("OBSERVABILITY_ENV", "").strip() or settings.app_env or "local"
    ).lower()


def _version() -> str:
    return os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0"


def _metric_sum(name: str, *, since: float) -> float:
    return sum(sample.value for sample in recent_metric_samples(since=since, name=name))


def _metric_latest(name: str) -> float | None:
    samples = recent_metric_samples(name=name)
    if not samples:
        return None
    return samples[-1].value


def _series_from_buffer(name: str, *, unit: str, since: float) -> NamedMetricSeries:
    samples = recent_metric_samples(since=since, name=name)
    points = [
        {"timestamp": _iso(datetime.fromtimestamp(sample.timestamp, tz=UTC)), "value": sample.value}
        for sample in samples
    ]
    total = sum(sample.value for sample in samples) if samples else None
    latest = samples[-1].value if samples else None
    return NamedMetricSeries(name=name, unit=unit, points=points, latest=latest, sum=total)


def _series_from_cloudwatch(
    name: str,
    *,
    unit: str,
    points: list[tuple[datetime, float]],
) -> NamedMetricSeries:
    serialized = [{"timestamp": _iso(stamp), "value": value} for stamp, value in points]
    latest = points[-1][1] if points else None
    total = sum(value for _stamp, value in points) if points else None
    return NamedMetricSeries(name=name, unit=unit, points=serialized, latest=latest, sum=total)


def _probe_payloads() -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """Readiness returns ``(payload, ready)``; never let probe shape crash /ops."""
    try:
        payload, ready = build_readiness_payload()
    except Exception:
        logger.warning("Readiness probe failed while assembling ops snapshot", exc_info=True)
        payload, ready = {}, False
    if not isinstance(payload, dict):
        payload, ready = {}, False
    try:
        health = build_health_payload()
    except Exception:
        logger.warning("Health probe failed while assembling ops snapshot", exc_info=True)
        health = {}
    if not isinstance(health, dict):
        health = {}
    return payload, bool(ready), health


def _health_summary(settings: Settings) -> HealthSummary:
    payload, ready, health = _probe_payloads()
    database = str((payload.get("database") or {}).get("status") or "unknown")
    configuration = str((payload.get("config") or {}).get("status") or "unknown")
    return HealthSummary(
        ready=ready,
        live=str(health.get("status") or "") in {"ok", "degraded"},
        database=database,
        configuration=configuration,
        version=_version(),
        env=_env(settings),
        deployedAt=None,
    )


def _worker_summaries(now: int) -> list[WorkerQueueSummary]:
    ai_jobs = get_ai_job_store().list()
    redaction_jobs = get_redaction_job_store().list()
    deliveries = []
    store = get_notification_delivery_store()
    list_all = getattr(store, "list_all", None)
    list_recent = getattr(store, "list_recent", None)
    if callable(list_recent):
        deliveries = list_recent(limit=200)
    elif callable(list_all):
        deliveries = list_all()

    def _age(jobs, statuses: set[str]) -> int | None:
        active = [job for job in jobs if job.status in statuses]
        if not active:
            return None
        return max(0, now - min(job.created_at for job in active))

    ai_errors = [
        sanitize_ops_text(getattr(job, "last_error", None), max_len=80)
        for job in ai_jobs
        if job.status == "dead_lettered"
    ]
    redaction_errors = [
        sanitize_ops_text(getattr(job, "last_error_code", None), max_len=80)
        for job in redaction_jobs
        if job.status == "dead_lettered"
    ]
    return [
        WorkerQueueSummary(
            kind="ai",
            label="AI classification",
            deployed=True,
            pending=sum(job.status == "queued" for job in ai_jobs),
            running=sum(job.status == "running" for job in ai_jobs),
            succeeded=sum(job.status == "succeeded" for job in ai_jobs),
            deadLettered=sum(job.status == "dead_lettered" for job in ai_jobs),
            oldestAgeSeconds=_age(ai_jobs, {"queued", "running"}),
            retries=sum(job.attempts for job in ai_jobs),
            lastErrorCode=next((code for code in ai_errors if code), None),
        ),
        WorkerQueueSummary(
            kind="redaction",
            label="Image redaction",
            deployed=True,
            pending=sum(job.status == "queued" for job in redaction_jobs),
            running=sum(job.status == "running" for job in redaction_jobs),
            succeeded=sum(job.status == "succeeded" for job in redaction_jobs),
            deadLettered=sum(job.status == "dead_lettered" for job in redaction_jobs),
            oldestAgeSeconds=_age(redaction_jobs, {"queued", "running"}),
            retries=sum(job.attempts for job in redaction_jobs),
            lastErrorCode=next((code for code in redaction_errors if code), None),
        ),
        WorkerQueueSummary(
            kind="notifications",
            label="Notifications",
            deployed=True,
            pending=0,
            running=0,
            succeeded=sum(item.attempt_status == "SUCCEEDED" for item in deliveries),
            deadLettered=sum(
                item.attempt_status in {"FAILED_PERMANENT", "FAILED_TRANSIENT"}
                for item in deliveries
            ),
            oldestAgeSeconds=None,
            retries=0,
            lastErrorCode=None,
        ),
        WorkerQueueSummary(
            kind="whatsapp",
            label="WhatsApp",
            deployed=False,
            lastErrorCode=None,
        ),
        WorkerQueueSummary(
            kind="moderation",
            label="Content safety",
            deployed=False,
            lastErrorCode=None,
        ),
    ]


def _safe_jobs(*, job_type: str | None = None) -> list[SafeJobRow]:
    rows: list[SafeJobRow] = []
    if job_type in {None, "ai"}:
        for job in get_ai_job_store().list():
            rows.append(
                SafeJobRow(
                    jobId=job.job_id,
                    kind="ai",
                    ticketId=hash_identifier(job.ticket_id),
                    status=job.status,
                    attempts=job.attempts,
                    createdAt=job.created_at,
                    updatedAt=job.updated_at,
                    lastErrorCode=sanitize_ops_text(job.last_error, max_len=80),
                    replayable=job.status == "dead_lettered",
                )
            )
    if job_type in {None, "redaction"}:
        for job in get_redaction_job_store().list():
            rows.append(
                SafeJobRow(
                    jobId=job.job_id,
                    kind="redaction",
                    ticketId=hash_identifier(job.ticket_id),
                    status=job.status,
                    attempts=job.attempts,
                    createdAt=job.created_at,
                    updatedAt=job.updated_at,
                    lastErrorCode=sanitize_ops_text(job.last_error_code, max_len=80),
                    replayable=job.status == "dead_lettered",
                )
            )
    rows.sort(key=lambda row: row.updated_at, reverse=True)
    return rows[:100]


def _product_metrics(since: float, municipality_id: str | None = None) -> ProductMetrics:
    tickets = get_ticket_store().list()
    if municipality_id:
        tickets = [ticket for ticket in tickets if ticket.municipality_id == municipality_id]
    notifications = []
    store = get_notification_delivery_store()
    list_all = getattr(store, "list_all", None)
    list_recent = getattr(store, "list_recent", None)
    if callable(list_recent):
        notifications = list_recent(limit=200)
    elif callable(list_all):
        notifications = list_all()
    channel_usage: Counter[str] = Counter()
    for item in notifications:
        channel = str(getattr(item, "channel", None) or "UNKNOWN")
        if channel in {"EMAIL", "SMS"}:
            channel_usage[channel] += 1
    municipalities = {ticket.municipality_id for ticket in tickets if ticket.municipality_id}
    return ProductMetrics(
        reportsSubmitted=int(_metric_sum("ReportsSubmitted", since=since))
        or sum(1 for _ticket in tickets),
        reportsFailed=int(_metric_sum("ReportsFailed", since=since)),
        ticketsOpen=sum(ticket.status in OPEN_TICKET_STATUSES for ticket in tickets),
        ticketsResolved=sum(ticket.status == "RESOLVED" for ticket in tickets),
        ticketsClosed=sum(ticket.status == "CLOSED" for ticket in tickets),
        activeMunicipalities=len(municipalities),
        notificationSucceeded=sum(item.attempt_status == "SUCCEEDED" for item in notifications),
        notificationFailed=sum(
            item.attempt_status in {"FAILED_PERMANENT", "FAILED_TRANSIENT"}
            for item in notifications
        ),
        channelUsage=dict(channel_usage),
    )


def _application_alerts(settings: Settings, since: float) -> list[AlertRecord]:
    _payload, ready, _health = _probe_payloads()
    derived: list[tuple[str, str, str, str]] = []
    if not ready:
        derived.append(
            (
                "BaladiGuard-ReadinessFailure",
                "ReadyProbeSuccess",
                "ALARM",
                "Readiness payload reports not ready.",
            )
        )
    if _metric_sum("Http5xx", since=since) >= 10:
        derived.append(
            (
                "BaladiGuard-Sustained5xx",
                "Http5xx",
                "ALARM",
                "Application metric buffer recorded a 5xx burst.",
            )
        )
    if _metric_sum("AuthFailures", since=since) >= 50:
        derived.append(
            (
                "BaladiGuard-AuthFailureSpike",
                "AuthFailures",
                "ALARM",
                "Application metric buffer recorded an auth-failure burst.",
            )
        )
    acks = {item.alarm_name: item for item in get_ops_alert_ack_store().list_all()}
    alerts: list[AlertRecord] = []
    seen: set[str] = set()
    for alarm_name, metric_name, state, reason in derived:
        seen.add(alarm_name)
        alerts.append(_alert_record(alarm_name, metric_name, state, reason, settings, acks))
    for alarm_name in ALARM_NAMES:
        if alarm_name in seen:
            continue
        runbook = runbook_for(alarm_name)
        metric_name = runbook.alarm_name.replace("BaladiGuard-", "") if runbook else "unknown"
        alerts.append(
            _alert_record(
                alarm_name,
                metric_name,
                "OK",
                "No local alarm condition.",
                settings,
                acks,
            )
        )
    return alerts


def _cloudwatch_alerts(
    raw_alarms: list[dict[str, Any]],
    settings: Settings,
) -> list[AlertRecord]:
    acks = {item.alarm_name: item for item in get_ops_alert_ack_store().list_all()}
    by_name = {str(alarm.get("AlarmName") or ""): alarm for alarm in raw_alarms}
    alerts: list[AlertRecord] = []
    for alarm_name in ALARM_NAMES:
        alarm = by_name.get(alarm_name)
        metric_name = str((alarm or {}).get("MetricName") or alarm_name)
        state = str((alarm or {}).get("StateValue") or "OK")
        reason = sanitize_ops_text((alarm or {}).get("StateReason"), max_len=160) or "OK"
        alerts.append(_alert_record(alarm_name, metric_name, state, reason, settings, acks))
    return alerts


def _alert_record(
    alarm_name: str,
    metric_name: str,
    state: str,
    reason: str,
    settings: Settings,
    acks: dict[str, StoredOpsAlertAck],
) -> AlertRecord:
    runbook = runbook_for(alarm_name)
    ack = acks.get(alarm_name)
    severity = runbook.severity if runbook else "unknown"
    if state.upper() == "OK":
        display_severity = "ok"
    else:
        display_severity = severity
    return AlertRecord(
        alarmName=alarm_name,
        metricName=metric_name,
        state=state,
        severity=display_severity,
        reason=sanitize_ops_text(reason, max_len=160) or "OK",
        runbookUrl=runbook.url if runbook else "docs/production-observability.md",
        awsConsoleUrl=alarm_console_url(region=settings.aws_region, alarm_name=alarm_name),
        ackStatus=ack.status if ack else "open",
        ackBy=ack.ack_by if ack else None,
        ackAt=ack.ack_at if ack else None,
        ackNote=sanitize_ops_text(ack.note, max_len=200) if ack else None,
        owner="developer_operator",
        firstSeen=None,
        lastSeen=_iso(),
    )


def _traffic_summary(since: float, cloudwatch_series: dict[str, list] | None) -> dict[str, Any]:
    def _value(name: str, reducer) -> float:
        if cloudwatch_series and name in cloudwatch_series and cloudwatch_series[name]:
            values = [point[1] for point in cloudwatch_series[name]]
            return float(reducer(values))
        if name == "HttpRequestDuration":
            latest = _metric_latest(name)
            return float(latest or 0.0)
        return float(_metric_sum(name, since=since))

    requests = _value("HttpRequests", sum)
    errors = _value("Http5xx", sum)
    error_rate = (errors / requests) if requests else 0.0
    return {
        "requests": requests,
        "errors": errors,
        "errorRate": round(error_rate, 4),
        "latencyMs": round(
            _value("HttpRequestDuration", lambda values: sum(values) / len(values)),
            2,
        ),
        "throttles": _value("RateLimitExceeded", sum),
        "authFailures": _value("AuthFailures", sum),
    }


def build_overview(
    *,
    time_range: str,
    service: str | None = None,
    severity: str | None = None,
    municipality_id: str | None = None,
    settings: Settings | None = None,
) -> OpsOverviewResponse:
    cfg = settings or get_settings()
    since = time.time() - TIME_RANGE_SECONDS[time_range]
    telemetry_source = "application"
    warning = None
    cloudwatch_series = None
    try:
        cloudwatch_series = fetch_metric_data(time_range=time_range, env=_env(cfg), settings=cfg)
        raw_alarms = describe_ops_alarms(env=_env(cfg), settings=cfg)
        alerts = _cloudwatch_alerts(raw_alarms, cfg)
        telemetry_source = "cloudwatch"
    except CloudWatchUnavailable as exc:
        warning = sanitize_ops_text(str(exc), max_len=160)
        alerts = _application_alerts(cfg, since)
        telemetry_source = "application"

    if service:
        alerts = [
            alert
            for alert in alerts
            if service in alert.metric_name.lower() or service in alert.alarm_name.lower()
        ]
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]

    backup_raw = backup_control_status(cfg)
    if backup_raw["status"] == "healthy":
        from app.core.metrics import emit_metric

        emit_metric("BackupControlSuccess", value=1.0, unit="None")
    elif backup_raw["status"] in {"degraded", "failed"}:
        from app.core.metrics import emit_metric

        emit_metric("BackupControlSuccess", value=0.0, unit="None")

    workers = _worker_summaries(int(time.time()))
    return OpsOverviewResponse(
        generatedAt=_iso(),
        telemetrySource=telemetry_source,
        telemetryWarning=warning,
        health=_health_summary(cfg),
        traffic=_traffic_summary(since, cloudwatch_series),
        workers=workers,
        alerts=alerts,
        product=_product_metrics(since, municipality_id),
        backup=BackupStatus(
            status=backup_raw["status"],  # type: ignore[arg-type]
            detail=backup_raw["detail"],
            source=backup_raw["source"],
        ),
        cloudwatchDashboardUrl=dashboard_console_url(region=cfg.aws_region),
        municipalityManagement=MUNICIPALITY_NAV,
    )


def build_metrics(
    *,
    time_range: str,
    settings: Settings | None = None,
) -> OpsMetricsResponse:
    cfg = settings or get_settings()
    since = time.time() - TIME_RANGE_SECONDS[time_range]
    units = {
        "HttpRequests": "Count",
        "Http5xx": "Count",
        "HttpRequestDuration": "Milliseconds",
        "ReadyProbeSuccess": "None",
        "AuthFailures": "Count",
        "RateLimitExceeded": "Count",
        "AiQueuePending": "Count",
        "AiProcessingFailed": "Count",
        "AiJobOldestAgeSeconds": "Seconds",
        "S3Errors": "Count",
        "DynamoDbErrors": "Count",
        "NotificationSucceeded": "Count",
        "NotificationFailed": "Count",
        "ImageRedactionJobsDeadLettered": "Count",
        "ReportsSubmitted": "Count",
        "ReportsFailed": "Count",
        "CitizensRegistered": "Count",
        "BackupControlSuccess": "None",
    }
    source = "application"
    try:
        cloudwatch_series = fetch_metric_data(time_range=time_range, env=_env(cfg), settings=cfg)
        source = "cloudwatch"
        series = [
            _series_from_cloudwatch(name, unit=unit, points=cloudwatch_series.get(name) or [])
            for name, unit in units.items()
        ]
    except CloudWatchUnavailable:
        series = [_series_from_buffer(name, unit=unit, since=since) for name, unit in units.items()]
    return OpsMetricsResponse(
        generatedAt=_iso(),
        telemetrySource=source,
        timeRange=time_range,  # type: ignore[arg-type]
        series=series,
    )


def list_alerts(
    *,
    time_range: str,
    severity: str | None = None,
    settings: Settings | None = None,
) -> list[AlertRecord]:
    overview = build_overview(time_range=time_range, severity=severity, settings=settings)
    return overview.alerts


def list_errors(
    *,
    category: str | None = None,
    service: str | None = None,
) -> list[ErrorGroup]:
    try:
        items = get_ops_error_store().list_recent(limit=50)
    except Exception:
        logger.warning("Ops error store list failed; returning an empty error list.", exc_info=True)
        items = []
    groups = [
        ErrorGroup(
            errorKey=item.error_key,
            category=item.category,
            service=item.service,
            pathGroup=item.path_group,
            statusClass=item.status_class,
            version=item.version,
            count=item.count,
            firstSeen=item.first_seen,
            lastSeen=item.last_seen,
            lastRequestId=item.last_request_id,
            lastJobId=item.last_job_id,
        )
        for item in items
    ]
    if category:
        groups = [item for item in groups if item.category == category]
    if service:
        groups = [item for item in groups if item.service == service]
    return groups


def list_workers(*, job_type: str | None = None) -> dict[str, Any]:
    summaries = _worker_summaries(int(time.time()))
    if job_type:
        summaries = [item for item in summaries if item.kind == job_type]
    return {
        "queues": [item.model_dump(by_alias=True) for item in summaries],
        "jobs": [item.model_dump(by_alias=True) for item in _safe_jobs(job_type=job_type)],
    }


def acknowledge_alert(
    alarm_name: str,
    actor: StaffPrincipal,
    *,
    note: str | None = None,
) -> AlertRecord:
    if not is_safe_alarm_name(alarm_name):
        raise ValueError("Unknown or unsafe alarm name.")
    stamped = _iso()
    stored = get_ops_alert_ack_store().put(
        StoredOpsAlertAck(
            alarmName=alarm_name,
            status="acknowledged",
            ackBy=actor.username,
            ackAt=stamped,
            note=sanitize_ops_text(note, max_len=200),
        )
    )
    get_ops_audit_store().append(
        StoredOpsAudit(
            auditId=f"ops_{uuid4().hex[:16]}",
            actionType="ALERT_ACKNOWLEDGED",
            actorStaffId=actor.staff_id,
            actorUsername=actor.username,
            target=alarm_name,
            summary="Alert acknowledged.",
            createdAt=stamped,
        )
    )
    runbook = runbook_for(alarm_name)
    settings = get_settings()
    return AlertRecord(
        alarmName=stored.alarm_name,
        metricName=stored.alarm_name,
        state="ALARM",
        severity=runbook.severity if runbook else "unknown",
        reason="Acknowledged by a developer operator.",
        runbookUrl=runbook.url if runbook else "docs/production-observability.md",
        awsConsoleUrl=alarm_console_url(region=settings.aws_region, alarm_name=alarm_name),
        ackStatus=stored.status,
        ackBy=stored.ack_by,
        ackAt=stored.ack_at,
        ackNote=stored.note,
        owner="developer_operator",
        lastSeen=stamped,
    )


def replay_job(job_id: str, actor: StaffPrincipal) -> ReplayJobResponse:
    if not is_safe_job_id(job_id):
        raise ValueError("Unknown or unsafe job id.")
    stamped = _iso()
    replayed = False
    action: str = "AI_JOB_REPLAYED"
    if job_id.startswith("ai:"):
        from app.services.ai_job_queue import ai_job_queue

        replayed = bool(ai_job_queue.replay(job_id))
        action = "AI_JOB_REPLAYED"
    elif job_id.startswith("redaction:"):
        from app.services.redaction.queue import image_redaction_queue

        replayed = bool(image_redaction_queue.replay(job_id))
        action = "REDACTION_JOB_REPLAYED"
    get_ops_audit_store().append(
        StoredOpsAudit(
            auditId=f"ops_{uuid4().hex[:16]}",
            actionType=action,  # type: ignore[arg-type]
            actorStaffId=actor.staff_id,
            actorUsername=actor.username,
            target=job_id,
            summary="Durable job replay requested." if replayed else "Job replay rejected.",
            createdAt=stamped,
        )
    )
    return ReplayJobResponse(jobId=job_id, replayed=replayed)


def record_http_error(
    *,
    path_group: str,
    status_code: int,
    request_id: str | None,
) -> None:
    from app.schemas.stored_ops import StoredOpsErrorGroup

    if status_code < 500:
        return
    category = "http_5xx"
    service = "api"
    if path_group.startswith("/v1/staff"):
        service = "auth"
    key = f"{service}:{category}:{path_group}:{status_code // 100}xx"
    stamped = _iso()
    try:
        get_ops_error_store().upsert(
            StoredOpsErrorGroup(
                errorKey=key[:120],
                category=category,
                service=service,
                pathGroup=path_group,
                statusClass=f"{status_code // 100}xx",
                version=_version(),
                count=1,
                firstSeen=stamped,
                lastSeen=stamped,
                lastRequestId=request_id,
                lastJobId=None,
            )
        )
    except Exception:
        logger.warning("Failed to persist an ops HTTP error group.", exc_info=True)


def record_job_error(*, service: str, category: str, job_id: str, reason: str | None) -> None:
    from app.schemas.stored_ops import StoredOpsErrorGroup

    stamped = _iso()
    safe_reason = sanitize_ops_text(reason, max_len=80) or "provider_error"
    key = f"{service}:{category}:{safe_reason}"
    try:
        get_ops_error_store().upsert(
            StoredOpsErrorGroup(
                errorKey=key[:120],
                category=category,
                service=service,
                pathGroup=None,
                statusClass=None,
                version=_version(),
                count=1,
                firstSeen=stamped,
                lastSeen=stamped,
                lastRequestId=None,
                lastJobId=job_id,
            )
        )
    except Exception:
        logger.warning("Failed to persist an ops job error group.", exc_info=True)


__all__ = [
    "acknowledge_alert",
    "all_runbooks",
    "build_metrics",
    "build_overview",
    "list_alerts",
    "list_errors",
    "list_workers",
    "record_http_error",
    "record_job_error",
    "redact_text",
    "replay_job",
]
