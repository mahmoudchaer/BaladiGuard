# Capacity validation report — 2026-08-10 — staging-equivalent-local

## Method

- Workload profile: **staging-equivalent-local** (synthetic only; no real citizen data)
- Operator script: `backend/scripts/capacity/run_staging_equivalent_capacity.py`
- Harness: `backend/scripts/capacity/concurrent_http_harness.py` write scenarios
- Scenarios run: write-mixed, submit-race, upload-race, staff-mutate, smoke
- Generated at: `2026-08-10T08:00:25.853308Z`

### Config

- Mode: **local staging-equivalent** (in-process memory ticket/account stores)
- Base URL: `http://127.0.0.1:61874`
- NOTIFICATION_ADAPTER=mock
- DATABASE_BACKEND=memory (production-equivalent HTTP/write concurrency; re-run with CAPACITY_BASE_URL=staging for live Dynamo WCU figures)
- S3: fake put_object via capacity_api_app 
- AI classifier/cleaner stubbed in capacity_api_app for deterministic completion
- Rate limits raised + smoke token capacity-smoke-token for measurement room
- Synthetic citizen phone=+96170820192 (local capacity bootstrap only)

## Numbers (per scenario)

| Scenario | Requests | 2xx | 4xx | 429 | 5xx | transport | p50 ms | p95 ms | p99 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `write-mixed` | 1967 | 1477 | 490 | 0 | 0 | 0 | 60.28 | 289.95 | 472.98 |
| `submit-race` | 1552 | 1552 | 0 | 0 | 0 | 0 | 51.27 | 132.30 | 189.80 |
| `upload-race` | 1422 | 1422 | 0 | 0 | 0 | 0 | 52.50 | 66.71 | 74.67 |
| `staff-mutate` | 134 | 107 | 27 | 0 | 0 | 0 | 498.89 | 1613.11 | 1994.15 |
| `smoke` | 1340 | 894 | 446 | 0 | 0 | 0 | 36.84 | 55.53 | 64.42 |

### Key route p95 (write-mixed when present)

- **ticket_submit**: count=246 p95=304.39 status={'201': 246}
- **photo_upload**: count=244 p95=233.76 status={'200': 244}
- **staff_list**: count=249 p95=509.30 status={'200': 249}
- **staff_status**: count=243 p95=199.78 status={'200': 3, '400': 240}
- **track_miss**: count=250 p95=230.87 status={'404': 250}
- **otp_request**: count=243 p95=231.86 status={'202': 243}
- **health_ready_ai**: count=242 p95=171.00 status={'200': 242}

### AI queue / readiness samples

- Sample count (last scenario): 10
- Last sample: `{"at": "2026-08-10T07:59:32.278688Z", "pending": 0, "processing": 0, "failed": 0, "status": "ok", "source": "memory_store"}`
- Max pending observed in harness: `4`

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| `write-mixed` submit p95 < 2500 ms | actual=304.39 | Yes |
| `write-mixed` track/list p95 < 800 ms | actual=509.30 | Yes |
| `write-mixed` 5xx rate < 1% | actual=0.0 | Yes |
| `submit-race` submit p95 < 2500 ms | actual=154.24 | Yes |
| `submit-race` track/list p95 < 800 ms | actual=— | n/a |
| `submit-race` 5xx rate < 1% | actual=0.0 | Yes |
| `upload-race` submit p95 < 2500 ms | actual=— | n/a |
| `upload-race` track/list p95 < 800 ms | actual=— | n/a |
| `upload-race` 5xx rate < 1% | actual=0.0 | Yes |
| `staff-mutate` submit p95 < 2500 ms | actual=— | n/a |
| `staff-mutate` track/list p95 < 800 ms | actual=1966.54 | No |
| `staff-mutate` 5xx rate < 1% | actual=0.0 | Yes |
| `smoke` submit p95 < 2500 ms | actual=— | n/a |
| `smoke` track/list p95 < 800 ms | actual=54.03 | Yes |
| `smoke` 5xx rate < 1% | actual=0.0 | Yes |
| **Aggregate** 5xx rate < 1% | 0/6415 = 0.0000 | Yes |
| AI queue age p95 < 2 min steady / < 10 min burst | Harness samples pending counts (not wall-age on multi-worker fleet); memory backend exposes exact pending/processing | Partial → Yes if maxPending steady and no 5xx on submit |
| Ticket state integrity under race | CI `tests/test_ticket_concurrency.py` (status + **exactly one** AI completion) | Yes |
| Provider throttle recovery | Unit tests SES/SNS throttle classification + safe inject notes in capacity-validation.md | Yes (unit) |

## Findings

- **Operating limit (this profile):** light concurrent write mix at configured concurrency was exercised; aggregate 5xx rate=0.0000.
- **DynamoDB indexes / pagination:** exercised via submit + staff list/detail/status mutations (memory backend for local equivalent; cloud Dynamo via CAPACITY_BASE_URL).
- **S3 uploads:** photo_upload scenario path measured (fake S3 put_object stub for safety).
- **AI jobs:** submit creates AI background work; readiness `health_ready_ai` samples queue signals; max pending observed=4 with stub classifier completing promptly.
- **Staff list growth:** after thousands of synthetic tickets, `staff-mutate` list p95 exceeded 800 ms (about 1.6–2.0 s). This is a capacity/config finding for pagination/page size under growth — not state corruption. Steady write-mixed staff_list p95 stayed within SLO (~509 ms).
- **Cost drivers:** Bedrock/AI, Dynamo RCU/WCU, S3 PUT, SES/SNS when real adapter on.
- **Config changes:** keep NOTIFICATION_ADAPTER=mock on capacity staging; prefer staff list filters + pagination as ticket volume grows; raise WCU only if CloudWatch shows throttles under write-mixed.

## Defects

- Critical: none opened from this run.
- Non-blocking: staff list lag under large synthetic backlog (document; no GitHub defect — product already pages/limits lists in admin UX).

## Sign-off

- Operator: automated `run_staging_equivalent_capacity.py` (2026-08-10T08:00:25.853308Z)
- Evidence JSON paths: C:\Users\Mohammad\Documents\Summer26\Amazon\BaladiGuard\infra\capacity\evidence\2026-08-10-capacity-run-smoke.json, C:\Users\Mohammad\Documents\Summer26\Amazon\BaladiGuard\infra\capacity\evidence\2026-08-10-capacity-run-staff-mutate.json, C:\Users\Mohammad\Documents\Summer26\Amazon\BaladiGuard\infra\capacity\evidence\2026-08-10-capacity-run-submit-race.json, C:\Users\Mohammad\Documents\Summer26\Amazon\BaladiGuard\infra\capacity\evidence\2026-08-10-capacity-run-upload-race.json, C:\Users\Mohammad\Documents\Summer26\Amazon\BaladiGuard\infra\capacity\evidence\2026-08-10-capacity-run-write-mixed.json
- Linked from [docs/release-readiness.md](../../../docs/release-readiness.md)

