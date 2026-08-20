"""Static runbooks and alarm ownership for the developer-operator dashboard."""

from __future__ import annotations

from app.schemas.ops import RunbookEntry

RUNBOOK_BASE = "docs/production-observability.md"

_RUNBOOKS: tuple[RunbookEntry, ...] = (
    RunbookEntry(
        alarmName="BaladiGuard-Sustained5xx",
        title="Sustained HTTP 5xx",
        severity="critical",
        owner="developer_operator",
        summary="API errors are sustained across two 5-minute windows.",
        steps=[
            "Confirm readiness and DynamoDB/S3 widgets before a rollback.",
            "Use request_id / X-Request-Id from the Errors view; never search raw ticket text.",
            "Check the latest deploy version on the overview card.",
        ],
        url=f"{RUNBOOK_BASE}#sustained-5xx",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-ReadinessFailure",
        title="Readiness probe failure",
        severity="critical",
        owner="developer_operator",
        summary="The API has been unready for three consecutive minutes.",
        steps=[
            "Hit GET /health/ready and inspect database/config (no secrets).",
            "Confirm APP_ENV, table prefix, and IAM for DescribeTable.",
            "Do not restart in a loop if configuration validation is aborting startup.",
        ],
        url=f"{RUNBOOK_BASE}#readiness-failure",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-HighLatency",
        title="High API latency",
        severity="warning",
        owner="developer_operator",
        summary="Average HTTP duration stayed above the evaluated threshold.",
        steps=[
            "Compare HttpRequestDuration with DynamoDbErrors and S3Errors.",
            "Check worker backlog; a stuck AI/redaction queue can stall writes.",
            "Review recent deploys on the overview version card.",
        ],
        url=f"{RUNBOOK_BASE}#high-latency",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-ThrottlingSpike",
        title="Request throttling spike",
        severity="warning",
        owner="developer_operator",
        summary="Abuse/rate-limit rejections are elevated.",
        steps=[
            "Confirm RateLimitExceeded vs AuthFailures to distinguish abuse from outage.",
            "Do not disable rate limits to 'fix' the alarm.",
            "If legitimate traffic, raise only the documented policy after review.",
        ],
        url=f"{RUNBOOK_BASE}#throttling",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-AiQueueBacklog",
        title="AI queue backlog",
        severity="critical",
        owner="developer_operator",
        summary="Pending AI jobs stayed above the backlog threshold.",
        steps=[
            "Check the AI worker process and Bedrock model access.",
            "Replay only dead-lettered jobs after confirming the ticket still exists.",
            "Watch AiJobOldestAgeSeconds for stuck claims.",
        ],
        url=f"{RUNBOOK_BASE}#ai-queue-backlog",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-AiProcessingFailures",
        title="AI processing failures",
        severity="critical",
        owner="developer_operator",
        summary="Terminal AI failures spiked.",
        steps=[
            "Inspect dead-letter reason codes only; never raw descriptions.",
            "Distinguish provider outages from missing tickets.",
            "Replay a single job first before bulk recovery.",
        ],
        url=f"{RUNBOOK_BASE}#ai-failures",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-StuckAiJobs",
        title="Stuck AI jobs",
        severity="critical",
        owner="developer_operator",
        summary="The oldest active AI job exceeded the age threshold.",
        steps=[
            "Confirm the AI worker is running and claiming jobs.",
            "Check claim timeouts (AI_JOB_TIMEOUT_SECONDS).",
            "Recover stale claims via the worker; do not delete queue rows.",
        ],
        url=f"{RUNBOOK_BASE}#stuck-ai-jobs",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-RedactionFailures",
        title="Image redaction failures",
        severity="critical",
        owner="developer_operator",
        summary="Redaction jobs are dead-lettering.",
        steps=[
            "Keep public images fail-closed; never publish private originals.",
            "Check Rekognition IAM and detector configuration.",
            "Replay a dead-lettered job only after the source object still exists.",
        ],
        url=f"{RUNBOOK_BASE}#redaction-failures",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-StorageProviderErrors",
        title="S3 provider errors",
        severity="critical",
        owner="developer_operator",
        summary="Photo storage errors are sustained.",
        steps=[
            "Split S3 vs DynamoDB widgets.",
            "Check bucket policy, KMS, and network path.",
            "Do not paste presigned URLs into tickets or chat.",
        ],
        url=f"{RUNBOOK_BASE}#storage-provider-failures",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-DynamoDbErrors",
        title="DynamoDB errors",
        severity="critical",
        owner="developer_operator",
        summary="Persistence errors are sustained.",
        steps=[
            "Check throttling, missing tables, and wrong endpoint URL.",
            "Confirm table prefix matches APP_ENV.",
            "Do not scan production tables from the browser.",
        ],
        url=f"{RUNBOOK_BASE}#storage-provider-failures",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-NotificationFailureSpike",
        title="Notification delivery failures",
        severity="critical",
        owner="developer_operator",
        summary="Citizen notification failures spiked.",
        steps=[
            "Check NOTIFICATION_ADAPTER, SES sandbox, and SES_FROM_EMAIL.",
            "Use redacted destination hints only; never raw phone/email.",
            "Ticket writes must remain committed; retry via the notification path.",
        ],
        url=f"{RUNBOOK_BASE}#notification-failures",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-AuthFailureSpike",
        title="Authentication failure spike",
        severity="warning",
        owner="developer_operator",
        summary="Possible credential stuffing or a bad deploy of auth.",
        steps=[
            "Distinguish staff login vs citizen 401s via the kind dimension in logs.",
            "Confirm rate limits are engaging.",
            "Single wrong passwords are expected; only sustained spikes page.",
        ],
        url=f"{RUNBOOK_BASE}#auth-failures",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-BackupControlFailure",
        title="Backup control failure",
        severity="critical",
        owner="developer_operator",
        summary="Point-in-time recovery or backup controls are unhealthy.",
        steps=[
            "Run scripts/backup/backup_controls.py in audit mode.",
            "Do not restore over live table names.",
            "Follow docs/production-backup-restore.md isolation rules.",
        ],
        url="docs/production-backup-restore.md",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-WhatsAppAuthFailure",
        title="WhatsApp authentication failure",
        severity="warning",
        owner="developer_operator",
        summary="Placeholder until the WhatsApp channel is deployed.",
        steps=[
            "Confirm the WhatsApp worker is actually deployed before paging.",
            "Treat missing metrics as not-deployed, not as a silent outage.",
        ],
        url=f"{RUNBOOK_BASE}#whatsapp",
    ),
    RunbookEntry(
        alarmName="BaladiGuard-ModerationFailure",
        title="Content-safety worker failure",
        severity="warning",
        owner="developer_operator",
        summary="Placeholder until the content-safety pipeline is deployed.",
        steps=[
            "Confirm the moderation worker is actually deployed before paging.",
            "Keep public eligibility fail-closed if the pipeline is enabled.",
        ],
        url=f"{RUNBOOK_BASE}#moderation",
    ),
)


def runbook_for(alarm_name: str) -> RunbookEntry | None:
    for entry in _RUNBOOKS:
        if entry.alarm_name == alarm_name:
            return entry
    return None


def all_runbooks() -> list[RunbookEntry]:
    return list(_RUNBOOKS)
