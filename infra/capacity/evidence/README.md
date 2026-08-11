# Capacity evidence (issue #191)

Measured evidence and templates for capacity validation.

| File | Purpose |
| --- | --- |
| [staging-capacity-template.json](./staging-capacity-template.json) | Empty template matching harness output |
| [2026-08-11-staging-equivalent-capacity.md](./2026-08-11-staging-equivalent-capacity.md) | Latest local **harness smoke** report (not Dynamo staging) |
| [2026-08-11-staging-equivalent-capacity-combined.json](./2026-08-11-staging-equivalent-capacity-combined.json) | Combined multi-scenario JSON for the smoke run |
| `2026-08-11-capacity-run-*.json` | Per-scenario harness output |
| [2026-08-10-staging-equivalent-capacity.md](./2026-08-10-staging-equivalent-capacity.md) | Prior local run (historical) |
| [2026-08-09-ci-correctness-report.md](./2026-08-09-ci-correctness-report.md) | CI race-gate notes |

## Evidence classes

| Profile | How | Counts toward #191 Dynamo/S3 gate? |
| --- | --- | --- |
| `local-harness-smoke` | No `CAPACITY_BASE_URL`; memory + fake S3 | **No** — runner regression only |
| `staging-remote` | `CAPACITY_BASE_URL` + synthetic token; real Dynamo/S3 | **Yes** |

## How to regenerate local harness smoke

```bash
cd backend
PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
```

## How to capture production-equivalent staging evidence

```bash
export CAPACITY_BASE_URL=https://api.staging.example
export CAPACITY_CITIZEN_TOKEN=...   # contribution-ready synthetic user
export CAPACITY_STAFF_USER=admin
export CAPACITY_STAFF_PASSWORD=...
export CAPACITY_USE_REAL_S3=1
cd backend
PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
# Commit the resulting YYYY-MM-DD-* evidence + CloudWatch notes.
```

Scenario budgets always include `--max-requests` and `--min-interval-ms` so upload
workloads cannot unbounded-flood the API.

See [docs/capacity-validation.md](../../../docs/capacity-validation.md).
