# Capacity validation report — 2026-08-09 — CI / local correctness gates (#191)

## Method

- Profile: demo / CI memory backend (correctness under race; not multi-VU fleet)
- Suite:
  ```bash
  pytest tests/test_ticket_concurrency.py tests/test_citizen_account.py \
    tests/test_citizen_otp_auth.py tests/test_ai_submission_integration.py \
    tests/test_notifications.py tests/test_shared_rate_limiting.py \
    tests/test_notification_aws_adapter.py -q
  ```
- Staging HTTP harness: optional live run with
  `python scripts/capacity/concurrent_http_harness.py` (see runbook)

## Numbers

| Check | Result |
| --- | --- |
| Concurrent phone claim single winner | Covered (memory + Dynamo suite) |
| Concurrent OTP verify single winner | Covered |
| Concurrent ticket status / category / department | `tests/test_ticket_concurrency.py` |
| AI claim / process single completion | Covered + concurrency test |
| Notification multi-worker claim | Covered |
| Provider throttle classification | Unit tests (SES/SNS fake clients) |

Fill live staging latency histograms after a harness run against staging.

## Evaluation vs SLOs

| Target | Result | Pass? |
| --- | --- | --- |
| No state corruption under concurrent mutations | Green CI gates | Yes |
| p95 HTTP under model peak | Pending staging harness run | Partial |
| 5xx < 1% under light load | Pending staging harness run | Partial |

## Findings

- Operating limit for **correctness** races: covered in CI for phones, OTP, status, AI claim, notify ledger.
- Live **throughput** operating limits and WCU recommendations require one staging harness pass with CloudWatch.
- Email is intentionally non-unique; phone is the identity uniqueness boundary.
- Cost drivers: Bedrock AI, Dynamo RCU/WCU, S3 photo PUTs, SES/SNS when real adapter enabled.

## Defects

None opened as critical from the CI correctness gate suite.

## Sign-off

- Automated gates: 2026-08-09 (issue #191 implementation)
- Staging light-load numbers: run and attach JSON under `infra/capacity/evidence/`
