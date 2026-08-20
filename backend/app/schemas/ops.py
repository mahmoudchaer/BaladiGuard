"""Safe developer-operator dashboard models (issue #320).

These projections never include secrets, OTPs, full contacts, ticket text,
images, or AWS credentials.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

OpsTimeRange = Literal["1h", "6h", "24h", "7d"]
OpsSeverity = Literal["critical", "warning", "ok", "unknown"]
OpsAckStatus = Literal["open", "acknowledged"]
WorkerKind = Literal["ai", "redaction", "notifications", "whatsapp", "moderation"]
TelemetrySource = Literal["cloudwatch", "application", "mixed"]


class OpsFilters(BaseModel):
    time_range: OpsTimeRange = Field(default="1h", alias="range")
    service: str | None = None
    severity: OpsSeverity | None = None
    error_category: str | None = Field(default=None, alias="errorCategory")
    job_type: WorkerKind | None = Field(default=None, alias="jobType")
    municipality_id: str | None = Field(default=None, alias="municipalityId")

    model_config = {"populate_by_name": True}


class MetricPoint(BaseModel):
    timestamp: str
    value: float


class NamedMetricSeries(BaseModel):
    name: str
    unit: str
    points: list[MetricPoint] = Field(default_factory=list)
    latest: float | None = None
    sum: float | None = None


class HealthSummary(BaseModel):
    ready: bool
    live: bool
    database: str
    configuration: str
    version: str
    env: str
    deployed_at: str | None = Field(default=None, alias="deployedAt")

    model_config = {"populate_by_name": True}


class WorkerQueueSummary(BaseModel):
    kind: WorkerKind
    label: str
    deployed: bool
    pending: int = 0
    running: int = 0
    succeeded: int = 0
    dead_lettered: int = Field(default=0, alias="deadLettered")
    oldest_age_seconds: int | None = Field(default=None, alias="oldestAgeSeconds")
    retries: int = 0
    last_error_code: str | None = Field(default=None, alias="lastErrorCode")

    model_config = {"populate_by_name": True}


class SafeJobRow(BaseModel):
    job_id: str = Field(alias="jobId")
    kind: WorkerKind
    ticket_id: str = Field(alias="ticketId")
    status: str
    attempts: int = 0
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    last_error_code: str | None = Field(default=None, alias="lastErrorCode")
    replayable: bool = False

    model_config = {"populate_by_name": True}


class AlertRecord(BaseModel):
    alarm_name: str = Field(alias="alarmName")
    metric_name: str = Field(alias="metricName")
    state: str
    severity: OpsSeverity
    reason: str
    runbook_url: str = Field(alias="runbookUrl")
    aws_console_url: str | None = Field(default=None, alias="awsConsoleUrl")
    ack_status: OpsAckStatus = Field(alias="ackStatus")
    ack_by: str | None = Field(default=None, alias="ackBy")
    ack_at: str | None = Field(default=None, alias="ackAt")
    ack_note: str | None = Field(default=None, alias="ackNote")
    owner: str = "developer_operator"
    first_seen: str | None = Field(default=None, alias="firstSeen")
    last_seen: str | None = Field(default=None, alias="lastSeen")

    model_config = {"populate_by_name": True}


class ErrorGroup(BaseModel):
    error_key: str = Field(alias="errorKey")
    category: str
    service: str
    path_group: str | None = Field(default=None, alias="pathGroup")
    status_class: str | None = Field(default=None, alias="statusClass")
    version: str | None = None
    count: int
    first_seen: str = Field(alias="firstSeen")
    last_seen: str = Field(alias="lastSeen")
    last_request_id: str | None = Field(default=None, alias="lastRequestId")
    last_job_id: str | None = Field(default=None, alias="lastJobId")

    model_config = {"populate_by_name": True}


class ProductMetrics(BaseModel):
    reports_submitted: int = Field(alias="reportsSubmitted")
    reports_failed: int = Field(alias="reportsFailed")
    tickets_open: int = Field(alias="ticketsOpen")
    tickets_resolved: int = Field(alias="ticketsResolved")
    tickets_closed: int = Field(alias="ticketsClosed")
    active_municipalities: int = Field(alias="activeMunicipalities")
    notification_succeeded: int = Field(alias="notificationSucceeded")
    notification_failed: int = Field(alias="notificationFailed")
    channel_usage: dict[str, int] = Field(default_factory=dict, alias="channelUsage")

    model_config = {"populate_by_name": True}


class BackupStatus(BaseModel):
    status: Literal["healthy", "degraded", "failed", "not_applicable", "unknown"]
    detail: str
    source: str


class OpsOverviewResponse(BaseModel):
    generated_at: str = Field(alias="generatedAt")
    telemetry_source: TelemetrySource = Field(alias="telemetrySource")
    telemetry_warning: str | None = Field(default=None, alias="telemetryWarning")
    health: HealthSummary
    traffic: dict[str, Any]
    workers: list[WorkerQueueSummary]
    alerts: list[AlertRecord]
    product: ProductMetrics
    backup: BackupStatus
    cloudwatch_dashboard_url: str | None = Field(default=None, alias="cloudwatchDashboardUrl")
    municipality_management: dict[str, Any] = Field(alias="municipalityManagement")

    model_config = {"populate_by_name": True}


class OpsMetricsResponse(BaseModel):
    generated_at: str = Field(alias="generatedAt")
    telemetry_source: TelemetrySource = Field(alias="telemetrySource")
    time_range: OpsTimeRange = Field(alias="timeRange")
    series: list[NamedMetricSeries]

    model_config = {"populate_by_name": True}


class AcknowledgeAlertRequest(BaseModel):
    note: str | None = Field(default=None, max_length=200)

    @field_validator("note")
    @classmethod
    def bound_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > 200:
            raise ValueError("note must be at most 200 characters.")
        return trimmed


class ReplayJobResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    replayed: bool

    model_config = {"populate_by_name": True}


class RunbookEntry(BaseModel):
    alarm_name: str = Field(alias="alarmName")
    title: str
    severity: OpsSeverity
    owner: str
    summary: str
    steps: list[str]
    url: str

    model_config = {"populate_by_name": True}
