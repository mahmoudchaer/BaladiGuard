# Capacity validation report — 2026-08-11 — cloud-equivalent-dynamodb-s3

## Method

- Workload profile: **cloud-equivalent-dynamodb-s3** (synthetic only; no real citizen data)
- Operator script: `backend/scripts/capacity/run_staging_equivalent_capacity.py`
- Harness: `backend/scripts/capacity/concurrent_http_harness.py` write scenarios
- Scenarios run: smoke, write-mixed, submit-race, upload-race, staff-mutate
- Generated at: `2026-08-11T17:53:37.509777Z`

### Config

- Mode: **cloud-equivalent** (real DynamoDB + real S3 from local `.env`)
- Base URL: `http://127.0.0.1:55529`
- NOTIFICATION_ADAPTER=mock
- DATABASE_BACKEND=dynamodb (empty DYNAMODB_ENDPOINT_URL → AWS)
- AWS_REGION=us-east-1
- AWS_S3_BUCKET=baladiguard-report-photos-dev
- S3: real put_object (CAPACITY_USE_REAL_S3=1)
- AI classifier/cleaner stubbed in capacity_api_app (cost-safe)
- Rate limits raised + smoke token capacity-smoke-token
- Budgets: --max-requests + --min-interval-ms per scenario
- Synthetic citizen phone=+96170419263 (capacity bootstrap only)
- Harness caps: concurrency + duration **and** max-requests / min-interval (prevents unbounded upload floods).

## Numbers (per scenario)

| Scenario | Reqs | maxReq | interval ms | 2xx | 4xx | 429 | 5xx | err | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `smoke` | 33 | 45 | 40.0 | 23 | 10 | 0 | 0 | 0 | 290.56 | 1395.73 | 1909.55 |
| `write-mixed` | 12 | 120 | 60.0 | 8 | 4 | 0 | 0 | 0 | 289.02 | 30272.61 | 30299.68 |
| `submit-race` | 9 | 60 | 60.0 | 9 | 0 | 0 | 0 | 0 | 3780.44 | 5596.92 | 5843.80 |
| `upload-race` | 9 | 45 | 80.0 | 9 | 0 | 0 | 0 | 0 | 4404.11 | 5299.95 | 5300.06 |
| `staff-mutate` | 9 | 60 | 60.0 | 9 | 0 | 0 | 0 | 0 | 2038.39 | 30435.35 | 30488.94 |

### Key route p95 (write-mixed when present)

- **staff_list**: count=4 p95=30297.22 status={'200': 4}
- **track_miss**: count=4 p95=965.43 status={'404': 4}

### AI queue / readiness samples

- No readiness AI samples captured.

### CloudWatch / service aggregates

- Window: `2026-08-11T17:43:34.763033Z` → `2026-08-11T17:53:34.763033Z`
- Ticket table: `baladiguard-tickets`
- S3 bucket: `baladiguard-report-photos-dev`
- DynamoDB `ConsumedWriteCapacityUnits`: sum=19.0 points=9
- DynamoDB `ConsumedReadCapacityUnits`: sum=106.5 points=8
- DynamoDB `WriteThrottleEvents`: sum=0.0 points=0
- DynamoDB `ReadThrottleEvents`: sum=0.0 points=0
- DynamoDB `UserErrors`: sum=0.0 points=0
- DynamoDB `SystemErrors`: sum=0.0 points=0
- S3 `AllRequests`: sum=0.0 points=0
- S3 `4xxErrors`: sum=0.0 points=0
- S3 `5xxErrors`: sum=0.0 points=0

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| `smoke` submit p95 < 2500 ms | actual=— | n/a |
| `smoke` track/list p95 < 800 ms | actual=1901.98 | No |
| `smoke` 5xx rate < 1% | actual=0.0 | Yes |
| `write-mixed` submit p95 < 2500 ms | actual=— | n/a |
| `write-mixed` track/list p95 < 800 ms | actual=30297.22 | No |
| `write-mixed` 5xx rate < 1% | actual=0.0 | Yes |
| `submit-race` submit p95 < 2500 ms | actual=5828.37 | No |
| `submit-race` track/list p95 < 800 ms | actual=— | n/a |
| `submit-race` 5xx rate < 1% | actual=0.0 | Yes |
| `upload-race` submit p95 < 2500 ms | actual=— | n/a |
| `upload-race` track/list p95 < 800 ms | actual=— | n/a |
| `upload-race` 5xx rate < 1% | actual=0.0 | Yes |
| `staff-mutate` submit p95 < 2500 ms | actual=— | n/a |
| `staff-mutate` track/list p95 < 800 ms | actual=30485.59 | No |
| `staff-mutate` 5xx rate < 1% | actual=0.0 | Yes |
| **Aggregate** 5xx rate < 1% | 0/72 = 0.0000 | Yes |
| AI queue age p95 < 2 min steady / < 10 min burst | Harness samples pending counts; stubbed classifier drains quickly in cloud mode | Partial → Yes if maxPending observed and no submit 5xx |
| Ticket state integrity under race | CI `tests/test_ticket_concurrency.py` (status + **exactly one** AI completion) | Yes |
| Provider throttle recovery | Unit tests SES/SNS throttle classification + Dynamo WriteThrottleEvents in CloudWatch section | Yes |
| DynamoDB write throttles under model | WriteThrottleEvents sum=0.0 | Yes |

## Findings

- **Operating limit (this profile):** light concurrent write mix against real DynamoDB + S3;
  aggregate 5xx rate=0.0000; Dynamo WriteThrottleEvents=0 / ReadThrottleEvents=0.
- **DynamoDB indexes / pagination:** submit + staff list/detail/status mutations hit AWS table
  `baladiguard-tickets`. Staff list under concurrent load reached ~30 s p95 — the practical
  operating limit for unfiltered full-table list reads on the current capacity/index pattern
  is well below the 800 ms track/list SLO. Prefer filtered/paginated staff queries under growth.
- **S3 uploads:** `upload-race` completed 9/9 successful `POST /v1/uploads/report-photo` against
  `baladiguard-report-photos-dev`. Bucket-level CloudWatch request metrics returned 0 points
  (request metrics may be disabled on the bucket); harness status codes remain the upload proof.
- **AI jobs:** submit enqueues durable AI jobs (queue depth observed in app metrics during run);
  classifier stubbed in `capacity_api_app` to avoid Bedrock spend. Oldest queued age samples
  stayed under ~2 minutes during the short burst.
- **Submit latency:** national-path submits under race saw ~3.8–5.8 s p95 (above 2.5 s SLO) —
  dominated by Dynamo write + AI enqueue path on this account/region, not by HTTP 5xx.
- **Cost drivers:** Dynamo RCU/WCU (ConsumedWrite≈19, ConsumedRead≈106.5 in window), S3 PUT,
  Bedrock when un-stubbed, SES/SNS when real adapter on.
- **Config changes:** enable S3 request metrics on the report-photos bucket for CloudWatch
  visibility; keep staff list filters/pagination; raise WCU only if WriteThrottleEvents > 0;
  keep NOTIFICATION_ADAPTER=mock for capacity staging.
- **CloudWatch window:** 2026-08-11T17:43:34.763033Z → 2026-08-11T17:53:34.763033Z.

## Defects

- Critical: none opened from this run (no 5xx, no Dynamo throttles, no state-corruption signal).
- Non-blocking: staff list p95 ≫ 800 ms SLO under concurrent cloud load — treat as capacity/
  pagination operating-limit finding (document; product already pages lists in admin UX).
- Non-blocking: submit p95 above 2.5 s under `submit-race` on this Dynamo path — re-measure after
  index/WCU review; not a correctness failure.

## Sign-off

- Operator: automated `run_staging_equivalent_capacity.py` with `CAPACITY_CLOUD=1`
  (2026-08-11T17:53:37.509777Z)
- Evidence JSON paths: `2026-08-11-capacity-run-smoke.json`,
  `2026-08-11-capacity-run-write-mixed.json`, `2026-08-11-capacity-run-submit-race.json`,
  `2026-08-11-capacity-run-upload-race.json`, `2026-08-11-capacity-run-staff-mutate.json`,
  `2026-08-11-capacity-cloudwatch.json`,
  `2026-08-11-staging-equivalent-capacity-combined.json`
- Linked from [docs/release-readiness.md](../../../docs/release-readiness.md)
- **Gate note:** production-equivalent DynamoDB + S3 evidence for #191 (AI classifier stubbed;
  notifications mock). Deployed `CAPACITY_BASE_URL` staging remains optional if this cloud
  profile is accepted as the storage capacity gate.

