# Production observability runbook

Operator handoff for issue #185: structured logs, metrics, distinct health
probes, CloudWatch dashboards, and alerts that page on sustained failures — not
single expected blips.

## Probe contract

| Probe | Path | HTTP behavior | Use for |
| --- | --- | --- | --- |
| Liveness | `GET /health/live` | Always `200` while the process can answer | Container `HEALTHCHECK`, kube liveness |
| Readiness | `GET /health/ready` | `200` when DB + config OK; `503` otherwise | Load balancer / deploy gate |
| Composite | `GET /health` | Always `200` when process is up; body may be `degraded` | Humans, demos, dashboards |

AI queue depth is reported on readiness/composite for local memory backends and
published as CloudWatch metrics from AI workers / startup recovery in DynamoDB
deployments. Queue backlog **does not** fail readiness (it pages via
`AiQueuePending` instead of removing healthy capacity).

### Continuous readiness metric producer

Docker `HEALTHCHECK` uses `/health/live` on purpose. The
`BaladiGuard-ReadinessFailure` alarm therefore cannot rely on that probe.

Each API process runs an in-process publisher (`app.core.readiness_probe`) that
evaluates readiness and emits `ReadyProbeSuccess` every
`READINESS_PROBE_INTERVAL_SECONDS` (default `30`). Disable only for tests with
`READINESS_PROBE_PUBLISHER=false`. Load balancers may still poll `/health/ready`;
the publisher is the guaranteed CloudWatch signal so
`treatMissingData: breaching` does not false-page a healthy service.

Set `APP_VERSION` on deploy so logs and probe payloads show the running build.
CloudWatch EMF / alarm identity uses the stable dimension `env` only — never
`version` — so selectors survive deploys.

## Structured logs

Production should set:

```bash
LOG_FORMAT=json
LOG_LEVEL=INFO
APP_VERSION=<git-sha-or-release>
APP_ENV=production
# METRICS_EMF defaults to true when APP_ENV=production
```

Each JSON log line includes `timestamp`, `level`, `logger`, `message`,
`service`, `env`, `version`, and `request_id` when serving HTTP. Sensitive keys
matching password / token / secret / otp / credential / authorization patterns
are replaced with `[REDACTED]` in structured extras. Notification mock delivery
logs use redacted phone/email hints only.

Metric lines look like:

```text
metric_event name=Http5xx value=1.0 unit=Count env=production ...
```

When EMF is enabled, a second stdout JSON object (CloudWatch Embedded Metric
Format) is emitted for the `BaladiGuard` namespace.

## Metrics catalog

| Metric | Meaning |
| --- | --- |
| `HttpRequests` / `HttpRequestDuration` / `Http5xx` | Request count, latency, server errors |
| `AuthFailures` | Staff login / citizen 401 auth failures |
| `RateLimitExceeded` | Shared abuse limiter rejections |
| `DynamoDbErrors` / `S3Errors` | Persistence and photo-storage provider errors |
| `AiQueuePending` / `AiProcessingSucceeded` / `AiProcessingFailed` | AI queue health and terminal failures |
| `NotificationSucceeded` / `NotificationFailed` | Citizen notification outcomes |
| `ReadyProbeSuccess` | `1` ready / `0` not ready (from `/health/ready`) |

## Apply dashboard and alarms

From `backend/`, with production credentials:

```bash
python scripts/observability/apply_observability.py
python scripts/observability/apply_observability.py \
  --apply \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:baladiguard-ops \
  --output observability-evidence/latest.json
```

Checked-in definitions live under `infra/observability/`. Dry-run (default)
validates that every acceptance alarm exists, thresholds require multiple
datapoints, and descriptions link this runbook.

## Staging exercise (prove alerts reach the team)

Run in **staging** before production cutover. Record evidence (SNS delivery +
alarm history screenshots or JSON) in the ops evidence store.

Apply + automated readiness drill (required evidence artifact):

```bash
cd backend
python scripts/observability/apply_observability.py --apply --env staging \
  --alarm-actions "$STAGING_OPS_SNS_ARN" \
  --output observability-evidence/apply-staging.json
# Organic metric evaluation (CloudWatch must cross threshold) + SNS delivery:
python scripts/observability/staging_drill.py --live --env staging \
  --alarm-actions "$STAGING_OPS_SNS_ARN" \
  --organic-wait-seconds 240 \
  --output infra/observability/evidence/staging-drill-live.json
```

The drill records **three separate proofs** in one JSON artifact:

1. **`organicEvaluation`** — publishes `ReadyProbeSuccess` samples and applies the
   exact checked-in `Period=60`, `EvaluationPeriods=3`, and
   `DatapointsToAlarm=3` settings. Live mode polls until CloudWatch itself enters
   ALARM from those metrics; it never uses `SetAlarmState`. The artifact includes
   both the checked-in and applied policy so a weakened drill alarm cannot pass.
2. **`snsDelivery`** — in live mode, captures the AlarmActions/OKActions caused by
   those organic CloudWatch transitions and records sanitized notification /
   alarm-history payloads proving the ops topic received both states. Only moto
   simulation uses forced states to compensate for its alarm-action limitation.
3. **Recovery** — `recoveryVerified` must be true before `evidence.ok` is true.
   The live drill publishes one healthy point in each of three subsequent clean
   periods and requires CloudWatch's observed OK transition; it does not treat
   same-period healthy points as overwriting earlier zero samples.

Checked-in live evidence: `infra/observability/evidence/staging-drill-live.json`
(regenerate with the command above whenever the alarm policy or drill changes).

CI runs the same drill in **simulated** (moto) mode: organic verdicts from
samples + SNS→SQS capture of CloudWatch-shaped ALARM/OK messages + recovery
samples.

Manual supplements:

1. **Sustained 5xx**: temporarily point a staging dependency wrong or deploy a
   canary that returns 500 on a test route; generate >10 failures across two
   5-minute windows. Confirm `BaladiGuard-Sustained5xx` fires with request IDs
   visible in log groups.
2. **Readiness failure (organic)**: stop DynamoDB access so `/health/ready`
   returns `503` and the in-process publisher emits `ReadyProbeSuccess=0` for
   ≥3 minutes (complements the metric-sample organic section of the drill).
3. **Notification spike**: force the real adapter into a permanent failure
   category (invalid SES identity in staging) and emit >10 failures across two
   windows. Confirm `BaladiGuard-NotificationFailureSpike`.
4. Attach SNS messages / `staging-drill-live.json` showing alarm name, `env`
   dimension, and runbook link.

A single forced 500 or one bad login must **not** page — thresholds require
sustained datapoints.

## Triage playbooks

### Sustained 5xx

1. Open the BaladiGuard dashboard → HTTP 5xx widget; note start time.
2. Filter JSON logs for `"level": "ERROR"` and the deploy `version`.
3. Correlate `request_id` / `X-Request-Id` with the failing path group.
4. Check readiness and DynamoDB/S3 error widgets before rolling back.

### Readiness failure

1. Hit `/health/ready` and inspect `database` / `config` (no secret values).
2. Confirm `APP_ENV`, table prefix, and IAM for `DescribeTable` / ticket table.
3. Do not restart in a loop if config validation is aborting startup — fix env.

### AI queue backlog

1. Check `AiQueuePending` and `AiProcessingFailed`.
2. Confirm Bedrock model access and `AI_PROCESSING_CLAIM_TIMEOUT_SECONDS`.
3. Restart one healthy task to run startup recovery; watch pending decline.

### AI failures

1. Inspect logs for `AI processing failed` / partial success warnings.
2. Verify model id and region; distinguish provider outages from bad inputs.
3. Failed tickets remain staff-visible — do not re-submit citizen reports.

### Storage / provider failures

1. Split S3 vs DynamoDB widgets.
2. For `S3_UPLOAD_FAILED` (HTTP 502): bucket policy, KMS, and network path.
3. For DynamoDB: throttling, missing tables, wrong endpoint URL in prod.

### Notification failures

1. Check `NOTIFICATION_ADAPTER`, SES sandbox, and `SES_FROM_EMAIL`.
2. Prefer delivery ledger / redacted destination hints — never raw PII from logs.
3. Ticket mutations must remain committed; retry only via notification path.

### Auth failures

1. Distinguish staff login spikes from citizen 401s via `kind` dimension.
2. Confirm rate limits (`staff-login`, OTP policies) are engaging.
3. Single wrong passwords are expected; only sustained spikes page.

## Retention and access controls

| Telemetry | Retention | Access |
| --- | --- | --- |
| Application logs (CloudWatch Logs) | 30 days hot (staging 14 days); export optional to S3 for 365 days | Engineering + on-call roles only; no broad account-wide read |
| EMF / custom metrics | 15 months (CloudWatch standard) | Same ops roles; dashboards are read-only for developers |
| Alarms + SNS | Alarm history 14 days in console; SNS delivery logs per topic policy | Alarm actions limited to the ops SNS topic; no email blast to all staff |
| Evidence (staging drills) | Keep latest JSON + screenshots in the protected ops evidence store | Break-glass admin only for deletion |

Do not grant production log read access to citizen-facing support tools. PII in
tickets remains in DynamoDB with existing app authz — logs must keep redaction
rules above. Rotate SNS topic subscriptions when on-call rotations change.

## Local verification

```bash
cd backend
pytest tests/test_health.py tests/test_observability.py tests/test_logging_metrics.py -q
python scripts/observability/apply_observability.py
```
