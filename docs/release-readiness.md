# Release readiness index

Thin launch checklist index for Sprint 6 production path. Full infrastructure and
security scan ownership stays on their feature tickets (#74/#75/#115/#185/#186/#187/#191).

| Gate | Artifact | Status owner |
| --- | --- | --- |
| Env & config fail-closed | [configuration.md](./configuration.md) production checklist | Platform |
| Local / Secrets sync | [env-sync.md](./env-sync.md) | Platform |
| Cloud Dynamo/S3 path | [cloud-setup.md](./cloud-setup.md) | Platform |
| Observability & alarms | [production-observability.md](./production-observability.md) | Ops |
| Backup / restore RPO-RTO | [production-backup-restore.md](./production-backup-restore.md) | Ops |
| Rate limits | [rate-limiting-runbook.md](./rate-limiting-runbook.md) | API |
| **Load / concurrency / capacity (#191)** | [capacity-validation.md](./capacity-validation.md), [capacity-workload-model.md](./capacity-workload-model.md), evidence under `infra/capacity/evidence/` | API + Ops |
| MVP functional acceptance | [sprint6-mvp-acceptance.md](./sprint6-mvp-acceptance.md) | Product |
| Role-permission matrix | [sprint6-role-permission-matrix.md](./sprint6-role-permission-matrix.md) | Security |

## Capacity gate (#191)

Before public launch:

1. CI concurrency suite green (`capacity-validation.md` “Correctness gates”).  
2. At least one **staging / staging-equivalent** light-load + write run with synthetic data;
   save JSON/markdown evidence.  
   **Current evidence:**
   [`infra/capacity/evidence/2026-08-10-staging-equivalent-capacity.md`](../infra/capacity/evidence/2026-08-10-staging-equivalent-capacity.md)
   (regenerate via `scripts/capacity/run_staging_equivalent_capacity.py`).  
3. Review SLOs vs numbers; file critical defects; record operating limits and cost drivers.  
4. Confirm no unresolved **critical** capacity defects open against launch.

Do not confuse this with full #75 deployed smoke / rollback or multi-day soak tests.
