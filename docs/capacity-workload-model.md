# Capacity workload model (issue #191)

Hypothesis traffic model for BaladiGuard before public launch. Numbers are
**starting budgets** for staging capacity validation — re-measure with
`scripts/capacity/concurrent_http_harness.py` and CloudWatch before publishing
as hard SLOs.

Use **synthetic** accounts only (`capacitytest…` phones, disposable emails). Never
load real citizen data.

## Scope sizes

| Profile | Daily active citizens | Concurrent staff | Municipality notes |
| --- | --- | --- | --- |
| Demo / pilot | ≤ 200 | 2–5 | Single municipality |
| Small city (MVP launch) | 1k–5k | 10–25 | 1 municipality, few depts |
| Growth (post-MVP) | 10k+ | 50+ | Out of 3SP proof; scale workers later |

## Steady-state vs burst (HTTP)

Rates are **requests per second (RPS)** at API edge for the **small city**
profile. Burst = short 1–2 minute peaks (outage report spike, shift start).

| Workload | Steady RPS | Burst RPS | Primary route(s) | Rate-limit policy |
| --- | --- | --- | --- | --- |
| Report submit | 0.5–2 | 10 | `POST /v1/tickets` | `public-ticket-submission` |
| Photo upload | 0.5–2 | 8 | `POST /v1/uploads/report-photo` | `public-upload-report-photo` |
| Tracking lookup | 1–5 | 25 | `GET /v1/tickets/track/{code}` | `public-ticket-track` |
| Citizen OTP request | 0.2–1 | 5 | `POST /v1/citizen/auth/otp/request` | `citizen-otp-request` + domain |
| Citizen OTP verify | 0.2–1 | 5 | `POST /v1/citizen/auth/otp/verify` | `citizen-otp-verify` + domain |
| Citizen history | 0.5–2 | 10 | `GET /v1/citizen/me/tickets` | session-gated |
| Citizen profile | 0.2–1 | 5 | `GET/PATCH /v1/citizen/me` | session-gated |
| Location validate | 0.5–2 | 10 | `POST /v1/locations/validate` | `public-location-validate` |
| Staff list | 1–3 | 15 | `GET /v1/tickets` | staff token |
| Staff detail / mutations | 0.5–2 | 10 | status / category / department / merge | staff token |
| Staff login | rare | 5 | `POST /v1/staff/login` | `staff-login` |
| Health probes | 0.1–1 | 2 | `/health/*` | unrestricted |

### AI worker load (async)

| Signal | Steady | Burst | Notes |
| --- | --- | --- | --- |
| New AI jobs / min | ≈ submit RPS × 60 | 10× short burst | One job per successful ticket |
| Queue age p95 | < 2 min | < 10 min | See `AiQueuePending` / readiness body |
| Concurrent claims | 1 worker claim / ticket | multi-worker race-safe | Dynamo conditional claim |

## DynamoDB / S3 cost drivers

| Driver | Why it matters |
| --- | --- |
| Write capacity on tickets + GSI | Submit + status history + audit on every mutation |
| Read capacity on `ticketId` / owner GSI / tracking | Staff list+detail and history pagination |
| S3 PUT rate + size | Report photos (max 5MB) dominate storage IO |
| Bedrock invocations | Per-ticket AI; main **variable cost** at burst |
| SES / SNS | Ticket notifications when `NOTIFICATION_ADAPTER=real` |
| Rate-limit buckets table | Shared multi-instance counters (#186) |

## Uniqueness / consistency expectations

| Resource | Concurrent expectation |
| --- | --- |
| Phone claim | Exactly one winner under race (`PHONE_UNAVAILABLE` losers) |
| Email on citizen profile | **Not unique** by product design — no race for uniqueness |
| Staff username | Unique; sequential create conflicts |
| AI processing claim | Single winner across workers |
| Notification emit ledger | Idempotent claim; no double-success for same event key |
| Ticket status | Workflow transition rules; concurrent invalid transitions must not corrupt history |

## CI correctness gates (not load fleets)

Documented in [capacity-validation.md](./capacity-validation.md). Primary automated race suites:

- `tests/test_citizen_account.py` / `test_citizen_account_dynamodb.py` — phone claims  
- `tests/test_citizen_otp_auth.py` — concurrent OTP verify  
- `tests/test_ticket_concurrency.py` — concurrent staff mutations  
- `tests/test_ai_submission_integration.py` — AI claim single-winner  
- `tests/test_notifications.py` — multi-worker delivery claim  
- Provider throttle unit tests — `tests/test_notification_aws_adapter.py`

## Related

- [capacity-validation.md](./capacity-validation.md) — how to run / SLOs / report  
- [rate-limiting-runbook.md](./rate-limiting-runbook.md) — budgets and smoke token  
- [production-observability.md](./production-observability.md) — metrics and dashboards  
- [release-readiness.md](./release-readiness.md) — launch gate index  
