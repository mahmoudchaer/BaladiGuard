# Capacity evidence (issue #191)

Measured evidence and templates for capacity validation.

| File | Purpose |
| --- | --- |
| [2026-08-24-staging-remote-capacity.md](./2026-08-24-staging-remote-capacity.md) | **Latest deployed staging report** — real API, DynamoDB, S3, AI workers, and ECS Container Insights |
| [2026-08-24-staging-remote-capacity-combined.json](./2026-08-24-staging-remote-capacity-combined.json) | Latest combined deployed-staging evidence |
| [2026-08-24-staging-remote-capacity-cloudwatch.json](./2026-08-24-staging-remote-capacity-cloudwatch.json) | Latest application, DynamoDB, S3, and ECS CloudWatch aggregates |
| [staging-capacity-template.json](./staging-capacity-template.json) | Empty template matching harness output |
| [2026-08-11-staging-equivalent-capacity.md](./2026-08-11-staging-equivalent-capacity.md) | **Primary #191 report** — cloud DynamoDB + S3 |
| [2026-08-11-staging-equivalent-capacity-combined.json](./2026-08-11-staging-equivalent-capacity-combined.json) | Combined multi-scenario JSON |
| [2026-08-11-capacity-cloudwatch.json](./2026-08-11-capacity-cloudwatch.json) | Dynamo/S3 CloudWatch aggregates |
| `2026-08-11-capacity-run-*.json` | Per-scenario harness output |
| `2026-08-24-staging-remote-capacity-run-*.json` | Latest deployed-staging per-scenario harness output |
| [2026-08-10-staging-equivalent-capacity.md](./2026-08-10-staging-equivalent-capacity.md) | Historical local memory smoke |
| [2026-08-09-ci-correctness-report.md](./2026-08-09-ci-correctness-report.md) | CI race-gate notes |

## Evidence classes

| Profile | How | Counts toward #191 Dynamo/S3 gate? |
| --- | --- | --- |
| `local-harness-smoke` | Default runner (memory + fake S3) | **No** — runner regression only |
| `cloud-equivalent-dynamodb-s3` | `CAPACITY_CLOUD=1` with AWS `.env` | **Yes** |
| `staging-remote` | `CAPACITY_BASE_URL` + citizen token | **Yes** |

## Regenerate cloud-equivalent evidence (required for #191)

```bash
cd backend
# Uses DATABASE_BACKEND=dynamodb + AWS_* from backend/.env / repo .env
CAPACITY_CLOUD=1 PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
```

## Remote deployed staging (optional)

```bash
export CAPACITY_BASE_URL=https://api.staging.example
export CAPACITY_CITIZEN_TOKEN=...
export CAPACITY_STAFF_USER=admin
export CAPACITY_STAFF_PASSWORD=...
cd backend
PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
```

See [docs/capacity-validation.md](../../../docs/capacity-validation.md).
