# Capacity validation report — 2026-08-11 — local-harness-smoke

## Method

- Workload profile: **local-harness-smoke** (synthetic only; no real citizen data)
- Operator script: `backend/scripts/capacity/run_staging_equivalent_capacity.py`
- Harness: `backend/scripts/capacity/concurrent_http_harness.py` write scenarios
- Scenarios run: smoke, write-mixed, submit-race, upload-race, staff-mutate
- Generated at: `2026-08-11T13:24:02.807541Z`

### Config

- Mode: **local harness smoke** (NOT production-equivalent Dynamo/S3)
- Base URL: `http://127.0.0.1:52571`
- NOTIFICATION_ADAPTER=mock
- DATABASE_BACKEND=memory — use CAPACITY_BASE_URL for live Dynamo WCU/throttles
- S3: fake put_object via capacity_api_app 
- AI classifier/cleaner stubbed in capacity_api_app
- Rate limits raised + smoke token capacity-smoke-token
- Budgets: --max-requests + --min-interval-ms per scenario (anti-flood)
- Synthetic citizen phone=+96170865828 (local capacity bootstrap only)
- Harness caps: concurrency + duration **and** max-requests / min-interval (prevents unbounded upload floods).

## Numbers (per scenario)

| Scenario | Reqs | maxReq | interval ms | 2xx | 4xx | 429 | 5xx | err | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `smoke` | 80 | 80 | 25.0 | 53 | 27 | 0 | 0 | 0 | 8.40 | 33.20 | 47.31 |
| `write-mixed` | 240 | 240 | 40.0 | 180 | 60 | 0 | 0 | 0 | 17.57 | 51.30 | 1433.74 |
| `submit-race` | 160 | 160 | 40.0 | 160 | 0 | 0 | 0 | 0 | 15.66 | 35.93 | 51.27 |
| `upload-race` | 120 | 120 | 60.0 | 120 | 0 | 0 | 0 | 0 | 16.96 | 29.50 | 34.67 |
| `staff-mutate` | 100 | 100 | 50.0 | 80 | 20 | 0 | 0 | 0 | 45.34 | 190.23 | 217.72 |

### Key route p95 (write-mixed when present)

- **ticket_submit**: count=30 p95=45.87 status={'201': 30}
- **photo_upload**: count=30 p95=187.50 status={'200': 30}
- **staff_list**: count=30 p95=1520.58 status={'200': 30}
- **staff_status**: count=30 p95=39.12 status={'400': 29, '200': 1}
- **track_miss**: count=31 p95=27.11 status={'404': 31}
- **otp_request**: count=29 p95=35.04 status={'202': 29}
- **health_ready_ai**: count=27 p95=21.08 status={'200': 27}

### AI queue / readiness samples

- Sample count (last scenario): 10
- Last sample: `{"at": "2026-08-11T13:23:54.216295Z", "pending": 28, "processing": 0, "failed": 0, "status": "backlogged", "source": "memory_store"}`
- Max pending observed in harness: `34`

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| `smoke` submit p95 < 2500 ms | actual=— | n/a |
| `smoke` track/list p95 < 800 ms | actual=38.66 | Yes |
| `smoke` 5xx rate < 1% | actual=0.0 | Yes |
| `write-mixed` submit p95 < 2500 ms | actual=45.87 | Yes |
| `write-mixed` track/list p95 < 800 ms | actual=1520.58 | No |
| `write-mixed` 5xx rate < 1% | actual=0.0 | Yes |
| `submit-race` submit p95 < 2500 ms | actual=38.43 | Yes |
| `submit-race` track/list p95 < 800 ms | actual=— | n/a |
| `submit-race` 5xx rate < 1% | actual=0.0 | Yes |
| `upload-race` submit p95 < 2500 ms | actual=— | n/a |
| `upload-race` track/list p95 < 800 ms | actual=— | n/a |
| `upload-race` 5xx rate < 1% | actual=0.0 | Yes |
| `staff-mutate` submit p95 < 2500 ms | actual=— | n/a |
| `staff-mutate` track/list p95 < 800 ms | actual=215.39 | Yes |
| `staff-mutate` 5xx rate < 1% | actual=0.0 | Yes |
| **Aggregate** 5xx rate < 1% | 0/700 = 0.0000 | Yes |
| AI queue age p95 < 2 min steady / < 10 min burst | Harness samples pending counts (not wall-age on multi-worker fleet); memory backend exposes exact pending/processing | Partial → Yes if maxPending steady and no 5xx on submit |
| Ticket state integrity under race | CI `tests/test_ticket_concurrency.py` (status + **exactly one** AI completion) | Yes |
| Provider throttle recovery | Unit tests SES/SNS throttle classification + safe inject notes in capacity-validation.md | Yes (unit) |

## Findings

- **Operating limit (this profile):** light concurrent write mix with hard request budgets
  (≤240 reqs write-mixed, ≤120 upload-race); aggregate 5xx rate=0.0000; no transport errors.
- **DynamoDB indexes / pagination:** local memory only — re-run with `CAPACITY_BASE_URL` for WCU/throttle
  metrics. Staff list p95 under write-mixed exceeded 800 ms on a growing in-memory backlog
  (observation for pagination load; staff-mutate list stayed within target).
- **S3 uploads:** photo_upload path measured (fake S3 put_object stub for local smoke).
- **AI jobs:** submit creates AI work; readiness samples showed max pending ≈ 34 (backlog under stub
  worker; no submit 5xx).
- **Cost drivers:** Bedrock/AI, Dynamo RCU/WCU, S3 PUT, SES/SNS when real adapter on.
- **Config changes:** keep NOTIFICATION_ADAPTER=mock on capacity staging; raise WCU only if CloudWatch
  shows throttles under staging write-mixed.

## Defects

- Critical: none opened from this run.
- Non-blocking: staff list p95 under write-mixed on dense synthetic history (document;
  product already pages lists in admin UX).

## Sign-off

- Operator: automated `run_staging_equivalent_capacity.py` (2026-08-11T13:24:02.807541Z)
- Evidence JSON paths: `2026-08-11-capacity-run-smoke.json`,
  `2026-08-11-capacity-run-write-mixed.json`, `2026-08-11-capacity-run-submit-race.json`,
  `2026-08-11-capacity-run-upload-race.json`, `2026-08-11-capacity-run-staff-mutate.json`,
  `2026-08-11-staging-equivalent-capacity-combined.json`
- Linked from [docs/release-readiness.md](../../../docs/release-readiness.md)
- **Gate note:** this file is local harness smoke only. Production-equivalent staging still
  requires `CAPACITY_BASE_URL` + synthetic token against Dynamo/S3, then update this directory.

