# Capacity validation report — 2026-08-09 — CI correctness gates (#191)

CI-only foundation. **Full measured SLO evaluation:** see
[2026-08-10-staging-equivalent-capacity.md](./2026-08-10-staging-equivalent-capacity.md)
and companion JSON under this directory.

## Method

- Profile: demo / CI memory backend (correctness under race; not multi-VU fleet)
- Suite:
  ```bash
  pytest tests/test_ticket_concurrency.py tests/test_citizen_account.py \
    tests/test_citizen_otp_auth.py tests/test_ai_submission_integration.py \
    tests/test_notifications.py tests/test_shared_rate_limiting.py \
    tests/test_notification_aws_adapter.py -q
  ```
- Live write harness (supersedes “pending” rows below):
  `PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py`

## Numbers

| Check | Result |
| --- | --- |
| Concurrent phone claim single winner | Covered (memory + Dynamo suite) |
| Concurrent OTP verify single winner | Covered |
| Concurrent ticket status / category / department | `tests/test_ticket_concurrency.py` |
| AI claim / process single completion | **Exactly one** winner + terminal `completed` (fixed) |
| Notification multi-worker claim | Covered |
| Provider throttle classification | Unit tests (SES/SNS fake clients) |
| Live write p95 / 5xx / queue samples | See 2026-08-10 staging-equivalent evidence |

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| No state corruption under concurrent mutations | Green CI gates | Yes |
| p95 HTTP under model peak | Measured 2026-08-10 write-mixed (submit p95 ~304 ms) | Yes |
| 5xx < 1% under light load | Aggregate 0/6415 | Yes |

## Findings / defects

See 2026-08-10 report. No critical defect. Note: staff list p95 rose after a large
synthetic ticket backlog (`staff-mutate` scenario) — capacity finding for list/page
tuning under growth, not a corruption defect.

## Sign-off

- Automated gates: 2026-08-09
- Staging-equivalent write run: 2026-08-10 (`run_staging_equivalent_capacity.py`)
