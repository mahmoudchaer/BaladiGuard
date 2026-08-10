# Capacity evidence (issue #191)

Measured evidence and templates for capacity validation.

| File | Purpose |
| --- | --- |
| [staging-capacity-template.json](./staging-capacity-template.json) | Empty template matching harness output |
| [2026-08-10-staging-equivalent-capacity.md](./2026-08-10-staging-equivalent-capacity.md) | **Primary report** — SLO evaluation + findings |
| [2026-08-10-staging-equivalent-capacity-combined.json](./2026-08-10-staging-equivalent-capacity-combined.json) | Combined multi-scenario JSON |
| `2026-08-10-capacity-run-*.json` | Per-scenario harness output (write-mixed, submit, upload, staff-mutate, smoke) |
| [2026-08-09-ci-correctness-report.md](./2026-08-09-ci-correctness-report.md) | CI race-gate notes (links to 2026-08-10 for live numbers) |

## How to regenerate

```bash
cd backend
PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
```

Remote staging (when available):

```bash
# contribution-ready synthetic citizen token + staff admin
set CAPACITY_BASE_URL=https://api.staging.example
set CAPACITY_CITIZEN_TOKEN=...
set CAPACITY_STAFF_USER=admin
set CAPACITY_STAFF_PASSWORD=...
set CAPACITY_USE_REAL_S3=1
PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
```

See [docs/capacity-validation.md](../../../docs/capacity-validation.md).
