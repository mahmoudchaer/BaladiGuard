# Capacity validation runbook (issue #191)

Validate concurrency, light load, and operating limits **before public launch**.
This ticket is **not** a multi-day soak farm or full chaos suite.

| In scope | Out of scope |
| --- | --- |
| Workload model + SLO draft | 24h soak, 1k+ VU fleets |
| Staging-equivalent config, synthetic data only | Real citizen data |
| Light concurrent HTTP harness | Multi-region autoscaling proof |
| CI race / correctness tests | Full AWS FIS portfolio |
| Provider throttle unit tests + manual transient inject notes | Bedrock quality eval under load |

## Prerequisites

1. Staging or prod-like API with **synthetic** seed only (no production citizen PII).  
2. `APP_ENV` not `production` for exploratory injects, or a dedicated staging account.  
3. Production-equivalent storage: `DATABASE_BACKEND=dynamodb`, real S3 bucket for upload scenarios, `NOTIFICATION_ADAPTER=mock` unless deliberately testing SES/SNS with sandbox + allowlists.  
4. Optional: `RATE_LIMIT_SMOKE_BYPASS_TOKEN` set on the **server**; harness sends `X-BaladiGuard-Smoke-Token` so intentional higher quota still **enforces** a ceiling (see [rate-limiting-runbook.md](./rate-limiting-runbook.md)).  
5. Observer: CloudWatch dashboards / EMF from [production-observability.md](./production-observability.md).

## Service-level targets (initial)

Evaluate after a harness run; adjust only with evidence.

| Signal | Target (small-city model peak) | How to measure |
| --- | --- | --- |
| p95 HTTP latency (submit) | < 2.5 s (excluding AI completion) | `HttpRequestDuration` + harness histogram |
| p95 HTTP latency (track / staff list) | < 800 ms | same |
| 5xx rate | < 1% of requests under model | `Http5xx` / harness |
| Intentional 429 rate | Expected when above policy; not counted as failure if status is `RATE_LIMIT_EXCEEDED` | harness + `RateLimitExceeded` |
| AI queue age p95 | < 2 min steady; < 10 min short burst | `AiQueuePending` / readiness `aiQueue` |
| Recovery after transient fault | Back to green within 5 min of stop inject | manual observe + time stamp |
| Ticket state integrity | No corrupt status history; no dual AI success claims | post-run sampling + CI races |

Backup RPO/RTO remain under [production-backup-restore.md](./production-backup-restore.md) — separate from live HTTP capacity.

## Correctness gates (CI — always)

```bash
cd backend
py -3.11 -m pytest tests/test_ticket_concurrency.py tests/test_citizen_account.py tests/test_citizen_otp_auth.py tests/test_ai_submission_integration.py tests/test_notifications.py tests/test_shared_rate_limiting.py tests/test_notification_aws_adapter.py -q
```

Phone uniqueness under concurrent signup is covered here.
Email is **not** a uniqueness key (product rule); do not treat multi-user same-email as a defect.

## Light load harness (local or staging)

```bash
cd backend
# Against a running API (default http://127.0.0.1:8000)
PYTHONPATH=. python scripts/capacity/concurrent_http_harness.py --base-url http://127.0.0.1:8000 --scenario smoke --concurrency 8 --duration-seconds 20

# Staging example (synthetic only)
PYTHONPATH=. python scripts/capacity/concurrent_http_harness.py \
  --base-url https://api.staging.example \
  --scenario mixed \
  --concurrency 12 \
  --duration-seconds 60 \
  --smoke-token "$RATE_LIMIT_SMOKE_BYPASS_TOKEN" \
  --staff-user admin --staff-password "$STAFF_PASSWORD" \
  --output ../../infra/capacity/evidence/staging-capacity-run.json
```

Scenarios:

| Name | Behavior |
| --- | --- |
| `smoke` | Health + track/missing codes + readiness probes |
| `mixed` | Concurrent track, health, optional staff list if credentials given |
| `submit-race` | Requires `--citizen-token`; concurrent history + me reads (not create storms without OTP plumbing) |
| `staff-race` | Requires staff credentials; concurrent list + detail of a known ticket |

The harness records latency percentiles, status code histogram, and wall time. It **does not** delete clouds resources; use disposable staging.

### What to watch during the run

- DynamoDB throttles / `DynamoDbErrors`  
- S3 errors (upload scenario / separate `verify_cloud_report_flow.py`)  
- AI queue depth while synthetic submits run  
- Rate-limit 429 pattern vs policy tables  
- Provider throttling: mock or SES/SNS sandbox — unit tests already classify `Throttling` as transient  

## Safe transient-failure exercise

Keep bounded and reversible:

1. Pause AI worker process briefly → queue age rises → restart → jobs drain.  
2. Point one test client at a **wrong region** temporarily (do not leave it) to observe Dynamo error metrics, then restore.  
3. Rely on adapter unit tests for SES/SNS throttle codes rather than burning production SMS budgets.  

Never inject faults against production citizen data.

## Report template

Copy to `infra/capacity/evidence/YYYY-MM-DD-staging-capacity.md` (or fill JSON alongside).

```markdown
# Capacity validation report — <date> — <env>

## Method
- Workload profile: <demo | small city>
- Base URL, concurrency, duration, scenarios
- Smoke token used: yes/no
- Config summary: DATABASE_BACKEND, NOTIFICATION_ADAPTER, region

## Numbers
- Request count / success / 4xx / 5xx / 429
- Latency p50 / p95 / p99 (overall and key routes)
- Max AI queue depth observed
- Dynamo/S3 error counts if any

## Evaluation vs SLOs
| Target | Result | Pass? |
| --- | --- | --- |

## Findings
- Bottlenecks and config changes recommended
- Operating limits (max safe concurrency under current limits)
- Cost drivers (Bedrock, Dynamo, S3, SES/SNS)

## Defects
- Critical: link GitHub issues
- Non-blocking: link issues

## Sign-off
- Operator / date
```

Checked-in example skeleton: `infra/capacity/evidence/staging-capacity-template.json`.

## Defect policy

Critical corruption (split phone claim, double AI completion, broken status history under race) → open a **focused** GitHub issue and block launch.  
Capacity only (need higher WCU, longer AI worker) → document in report + escalate as config change.

## Links

- Workload model: [capacity-workload-model.md](./capacity-workload-model.md)  
- Release readiness gate: [release-readiness.md](./release-readiness.md)  
- Observability: [production-observability.md](./production-observability.md)  
- Rate limits: [rate-limiting-runbook.md](./rate-limiting-runbook.md)  
