# Capacity validation report — 2026-08-24 — staging-remote

## Method

- Workload profile: **staging-remote** (synthetic only; no real citizen data)
- Operator script: `backend/scripts/capacity/run_staging_equivalent_capacity.py`
- Harness: `backend/scripts/capacity/concurrent_http_harness.py` write scenarios
- Scenarios run: smoke, write-mixed, submit-race, upload-race, staff-mutate
- Generated at: `2026-08-24T16:25:54.187279Z`

### Config

- Mode: **remote / staging** via CAPACITY_BASE_URL
- Base URL: `https://api.staging.baladiguard.site`
- Harness caps: concurrency + duration **and** max-requests / min-interval (prevents unbounded upload floods).

## Numbers (per scenario)

| Scenario | Reqs | maxReq | interval ms | 2xx | 4xx | 429 | 5xx | err | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `smoke` | 76 | 80 | 25.0 | 51 | 25 | 0 | 0 | 0 | 410.41 | 466.17 | 743.83 |
| `write-mixed` | 173 | 240 | 40.0 | 133 | 40 | 0 | 0 | 0 | 806.09 | 2417.19 | 4277.06 |
| `submit-race` | 42 | 160 | 40.0 | 42 | 0 | 0 | 0 | 0 | 1336.32 | 3631.79 | 3875.72 |
| `upload-race` | 54 | 120 | 60.0 | 54 | 0 | 0 | 0 | 0 | 866.71 | 1965.14 | 2513.19 |
| `staff-mutate` | 39 | 100 | 50.0 | 34 | 5 | 0 | 0 | 0 | 1208.72 | 4532.59 | 5155.72 |

### Key route p95 (write-mixed when present)

- **ticket_submit**: count=23 p95=4638.33 status={'201': 23}
- **photo_upload**: count=24 p95=1994.22 status={'200': 24}
- **staff_list**: count=21 p95=1218.45 status={'200': 21}
- **staff_status**: count=21 p95=2124.14 status={'400': 19, '200': 2}
- **track_miss**: count=21 p95=484.64 status={'404': 21}
- **otp_request**: count=21 p95=1292.39 status={'202': 21}
- **health_ready_ai**: count=23 p95=945.38 status={'200': 23}

### AI queue / readiness samples

- Sample count (write-mixed): 10
- Last sample: `{"at": "2026-08-24T16:22:51.575574Z", "pending": null, "processing": null, "failed": null, "status": "metrics", "source": "worker_metrics"}`
- Max pending observed in harness: `None`

### Route coverage gate

- `smoke`: met minimum per-route samples
- `write-mixed`: met minimum per-route samples
- `submit-race`: met minimum per-route samples
- `upload-race`: met minimum per-route samples
- `staff-mutate`: met minimum per-route samples

### CloudWatch / service aggregates

- Window: `2026-08-24T16:14:06.444182Z` → `2026-08-24T16:24:06.444182Z`
- Ticket table: `baladiguard-staging-tickets`
- S3 bucket: `baladiguard-staging-report-photos-265911027282`
- DynamoDB `ConsumedWriteCapacityUnits`: sum=513.0 points=8
- DynamoDB `ConsumedReadCapacityUnits`: sum=36153.0 points=10
- DynamoDB `WriteThrottleEvents`: sum=0.0 points=0
- DynamoDB `ReadThrottleEvents`: sum=0.0 points=0
- DynamoDB `UserErrors`: sum=0.0 points=0
- DynamoDB `SystemErrors`: sum=0.0 points=0
- S3 `AllRequests`: sum=0.0 points=0
- S3 `4xxErrors`: sum=0.0 points=0
- S3 `5xxErrors`: sum=0.0 points=0
- BaladiGuard `HttpRequests` (Sum): value=422.0 points=10
- BaladiGuard `HttpRequestDurationP95` (p95): value=2657.1547201585245 points=10
- BaladiGuard `Http5xx` (Sum): value=0 points=0
- BaladiGuard `ReportsSubmitted` (Sum): value=39.0 points=2
- BaladiGuard `AiJobsQueued` (Sum): value=58.0 points=2
- BaladiGuard `AiJobsSucceeded` (Sum): value=40.0 points=2
- BaladiGuard `AiJobsRetried` (Sum): value=0 points=0
- BaladiGuard `AiJobsDeadLettered` (Sum): value=0 points=0
- BaladiGuard `AiJobOldestAgeSeconds` (Maximum): value=7.0 points=10
- ECS `api` `RunningTaskCount` (Minimum): value=1.0 points=10
- ECS `api` `CpuUtilized` (Average): value=318.36345336914064 points=9
- ECS `api` `MemoryUtilized` (Average): value=136.0 points=9
- ECS `ai-worker` `RunningTaskCount` (Minimum): value=1.0 points=10
- ECS `ai-worker` `CpuUtilized` (Average): value=133.2085400390625 points=9
- ECS `ai-worker` `MemoryUtilized` (Average): value=86.0 points=9
- ECS `redaction-worker` `RunningTaskCount` (Minimum): value=1.0 points=10
- ECS `redaction-worker` `CpuUtilized` (Average): value=117.7840625 points=10
- ECS `redaction-worker` `MemoryUtilized` (Average): value=80.0 points=10

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| `smoke` submit p95 < 2500 ms | actual=— | n/a |
| `smoke` track/list p95 < 800 ms | actual=476.41 | Yes |
| `smoke` 5xx rate < 1% | actual=0.0 | Yes |
| `smoke` min route coverage | missing={} | Yes |
| `write-mixed` submit p95 < 2500 ms | actual=4638.33 | No |
| `write-mixed` track/list p95 < 800 ms | actual=1218.45 | No |
| `write-mixed` 5xx rate < 1% | actual=0.0 | Yes |
| `write-mixed` min route coverage | missing={} | Yes |
| `submit-race` submit p95 < 2500 ms | actual=3734.85 | No |
| `submit-race` track/list p95 < 800 ms | actual=— | n/a |
| `submit-race` 5xx rate < 1% | actual=0.0 | Yes |
| `submit-race` min route coverage | missing={} | Yes |
| `upload-race` submit p95 < 2500 ms | actual=— | n/a |
| `upload-race` track/list p95 < 800 ms | actual=— | n/a |
| `upload-race` 5xx rate < 1% | actual=0.0 | Yes |
| `upload-race` min route coverage | missing={} | Yes |
| `staff-mutate` submit p95 < 2500 ms | actual=— | n/a |
| `staff-mutate` track/list p95 < 800 ms | actual=1997.03 | No |
| `staff-mutate` 5xx rate < 1% | actual=0.0 | Yes |
| `staff-mutate` min route coverage | missing={} | Yes |
| **Aggregate** 5xx rate < 1% | 0/384 = 0.0000 | Yes |
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
- **CloudWatch window:** 2026-08-24T16:14:06.444182Z -> 2026-08-24T16:24:06.444182Z.

## Defects

- Critical: none opened from this run.
- Non-blocking: `write-mixed` submitP95Ms exceeded target: actual=4638.33ms target=2500ms
- Non-blocking: `write-mixed` trackOrListP95Ms exceeded target: actual=1218.45ms target=800ms
- Non-blocking: `submit-race` submitP95Ms exceeded target: actual=3734.85ms target=2500ms
- Non-blocking: `staff-mutate` trackOrListP95Ms exceeded target: actual=1997.03ms target=800ms

## Sign-off

- Operator: automated `run_staging_equivalent_capacity.py` (2026-08-24T16:25:54.187279Z)
- Evidence JSON paths: see sibling JSON
- Linked from [docs/release-readiness.md](../../../docs/release-readiness.md)

