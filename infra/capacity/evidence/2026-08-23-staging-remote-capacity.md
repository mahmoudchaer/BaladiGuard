# Capacity validation report — 2026-08-23 — staging-remote

## Method

- Workload profile: **staging-remote** (synthetic only; no real citizen data)
- Operator script: `backend/scripts/capacity/run_staging_equivalent_capacity.py`
- Harness: `backend/scripts/capacity/concurrent_http_harness.py` write scenarios
- Scenarios run: smoke, write-mixed, submit-race, upload-race, staff-mutate
- Generated at: `2026-08-23T11:13:39.468169Z`

### Config

- Mode: **remote / staging** via CAPACITY_BASE_URL
- Base URL: `https://api.staging.baladiguard.site`
- Harness caps: concurrency + duration **and** max-requests / min-interval (prevents unbounded upload floods).

## Numbers (per scenario)

| Scenario | Reqs | maxReq | interval ms | 2xx | 4xx | 429 | 5xx | err | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `smoke` | 57 | 80 | 25.0 | 38 | 19 | 0 | 0 | 0 | 541.82 | 818.28 | 829.50 |
| `write-mixed` | 172 | 240 | 40.0 | 132 | 40 | 0 | 0 | 0 | 838.36 | 2295.67 | 4046.66 |
| `submit-race` | 47 | 160 | 40.0 | 47 | 0 | 0 | 0 | 0 | 1284.64 | 3195.91 | 3238.28 |
| `upload-race` | 63 | 120 | 60.0 | 63 | 0 | 0 | 0 | 0 | 851.99 | 1931.13 | 3233.03 |
| `staff-mutate` | 40 | 100 | 50.0 | 34 | 6 | 0 | 0 | 0 | 1228.99 | 3767.34 | 4737.88 |

### Key route p95 (write-mixed when present)

- **ticket_submit**: count=23 p95=4158.92 status={'201': 23}
- **photo_upload**: count=23 p95=2249.56 status={'200': 23}
- **staff_list**: count=21 p95=1531.64 status={'200': 21}
- **staff_status**: count=21 p95=1535.49 status={'400': 19, '200': 2}
- **track_miss**: count=21 p95=629.38 status={'404': 21}
- **otp_request**: count=21 p95=1271.11 status={'202': 21}
- **health_ready_ai**: count=23 p95=1074.20 status={'200': 23}

### AI queue / readiness samples

- Sample count (write-mixed): 10
- Last sample: `{"at": "2026-08-23T11:09:24.766808Z", "pending": null, "processing": null, "failed": null, "status": "metrics", "source": "worker_metrics"}`
- Max pending observed in harness: `None`

### Route coverage gate

- `smoke`: met minimum per-route samples
- `write-mixed`: met minimum per-route samples
- `submit-race`: met minimum per-route samples
- `upload-race`: met minimum per-route samples
- `staff-mutate`: met minimum per-route samples

### CloudWatch / service aggregates

- Window: `2026-08-23T11:00:45.549344Z` → `2026-08-23T11:10:45.549344Z`
- Ticket table: `baladiguard-staging-tickets`
- S3 bucket: `baladiguard-staging-report-photos-265911027282`
- DynamoDB `ConsumedWriteCapacityUnits`: sum=1103.0 points=6
- DynamoDB `ConsumedReadCapacityUnits`: sum=12757.5 points=10
- DynamoDB `WriteThrottleEvents`: sum=0.0 points=0
- DynamoDB `ReadThrottleEvents`: sum=0.0 points=0
- DynamoDB `UserErrors`: sum=0.0 points=0
- DynamoDB `SystemErrors`: sum=0.0 points=0
- S3 `AllRequests`: sum=0.0 points=0
- S3 `4xxErrors`: sum=0.0 points=0
- S3 `5xxErrors`: sum=0.0 points=0
- BaladiGuard `HttpRequests` (Sum): value=833.0 points=10
- BaladiGuard `HttpRequestDurationP95` (p95): value=1953.0729724098962 points=10
- BaladiGuard `Http5xx` (Sum): value=0 points=0
- BaladiGuard `ReportsSubmitted` (Sum): value=99.0 points=4
- BaladiGuard `AiJobsQueued` (Sum): value=150.0 points=4
- BaladiGuard `AiJobsSucceeded` (Sum): value=100.0 points=4
- BaladiGuard `AiJobsRetried` (Sum): value=0 points=0
- BaladiGuard `AiJobsDeadLettered` (Sum): value=0 points=0
- BaladiGuard `AiJobOldestAgeSeconds` (Maximum): value=7.0 points=10
- ECS `api` `RunningTaskCount` (Minimum): value=None points=0
- ECS `api` `CpuUtilized` (Average): value=None points=0
- ECS `api` `MemoryUtilized` (Average): value=None points=0
- ECS `ai-worker` `RunningTaskCount` (Minimum): value=None points=0
- ECS `ai-worker` `CpuUtilized` (Average): value=None points=0
- ECS `ai-worker` `MemoryUtilized` (Average): value=None points=0
- ECS `redaction-worker` `RunningTaskCount` (Minimum): value=None points=0
- ECS `redaction-worker` `CpuUtilized` (Average): value=None points=0
- ECS `redaction-worker` `MemoryUtilized` (Average): value=None points=0

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| `smoke` submit p95 < 2500 ms | actual=— | n/a |
| `smoke` track/list p95 < 800 ms | actual=819.43 | No |
| `smoke` 5xx rate < 1% | actual=0.0 | Yes |
| `smoke` min route coverage | missing={} | Yes |
| `write-mixed` submit p95 < 2500 ms | actual=4158.92 | No |
| `write-mixed` track/list p95 < 800 ms | actual=1531.64 | No |
| `write-mixed` 5xx rate < 1% | actual=0.0 | Yes |
| `write-mixed` min route coverage | missing={} | Yes |
| `submit-race` submit p95 < 2500 ms | actual=3234.91 | No |
| `submit-race` track/list p95 < 800 ms | actual=— | n/a |
| `submit-race` 5xx rate < 1% | actual=0.0 | Yes |
| `submit-race` min route coverage | missing={} | Yes |
| `upload-race` submit p95 < 2500 ms | actual=— | n/a |
| `upload-race` track/list p95 < 800 ms | actual=— | n/a |
| `upload-race` 5xx rate < 1% | actual=0.0 | Yes |
| `upload-race` min route coverage | missing={} | Yes |
| `staff-mutate` submit p95 < 2500 ms | actual=— | n/a |
| `staff-mutate` track/list p95 < 800 ms | actual=1352.09 | No |
| `staff-mutate` 5xx rate < 1% | actual=0.0 | Yes |
| `staff-mutate` min route coverage | missing={} | Yes |
| **Aggregate** 5xx rate < 1% | 0/379 = 0.0000 | Yes |
| AI queue age p95 < 2 min steady / < 10 min burst | CloudWatch max oldest age=7.0s across 10 points; readiness samples=23 | Yes |
| Ticket state integrity under race | CI `tests/test_ticket_concurrency.py` (status + **exactly one** AI completion) | Yes |
| Provider throttle recovery | Unit tests SES/SNS throttle classification + Dynamo WriteThrottleEvents in CloudWatch section | Yes |
| DynamoDB write throttles under model | WriteThrottleEvents sum=0.0 | Yes |

## Findings

- **Operating limit (this profile):** light concurrent write mix; aggregate 5xx rate=0.0000.
- **DynamoDB indexes / pagination:** exercised via submit + staff list/detail/status mutations (real DynamoDB).
- **S3 uploads:** photo_upload scenario path measured (real S3).
- **AI jobs:** deployed staging submits use the real AI worker/provider; readiness and CloudWatch capture queue age and completion signals.
- **Cost drivers:** Bedrock/AI, Dynamo RCU/WCU, S3 PUT, and enabled notifications.
- **Config changes:** raise capacity only if CloudWatch throttles or queue age breach the documented thresholds.
- **CloudWatch window:** 2026-08-23T11:00:45.549344Z -> 2026-08-23T11:10:45.549344Z.

## Defects

- Critical: none opened from this run.
- Non-blocking: `smoke` trackOrListP95Ms exceeded target: actual=819.43ms target=800ms
- Non-blocking: `write-mixed` submitP95Ms exceeded target: actual=4158.92ms target=2500ms
- Non-blocking: `write-mixed` trackOrListP95Ms exceeded target: actual=1531.64ms target=800ms
- Non-blocking: `submit-race` submitP95Ms exceeded target: actual=3234.91ms target=2500ms
- Non-blocking: `staff-mutate` trackOrListP95Ms exceeded target: actual=1352.09ms target=800ms

## Sign-off

- Operator: automated `run_staging_equivalent_capacity.py` (2026-08-23T11:13:39.468169Z)
- Evidence JSON paths: see sibling JSON
- Linked from [docs/release-readiness.md](../../../docs/release-readiness.md)
