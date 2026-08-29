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
| Security / abuse hardening (#316) | [security-hardening.md](./security-hardening.md) | API |
| **Load / concurrency / capacity (#191, #287)** | [capacity-validation.md](./capacity-validation.md), [capacity-workload-model.md](./capacity-workload-model.md), evidence under `infra/capacity/evidence/` | API + Ops |
| MVP functional acceptance | [sprint6-mvp-acceptance.md](./sprint6-mvp-acceptance.md) | Product |
| Role-permission matrix | [sprint6-role-permission-matrix.md](./sprint6-role-permission-matrix.md) | Security |

## Capacity gate (#191)

Before public launch:

1. CI concurrency suite green (`capacity-validation.md` “Correctness gates”).  
2. **Local harness smoke** (optional): default
   `scripts/capacity/run_staging_equivalent_capacity.py` — labeled
   `local-harness-smoke`, not Dynamo/S3 proof.  
3. At least one **production-equivalent** light-load + write run with synthetic data:
   - Preferred: `CAPACITY_CLOUD=1` against real DynamoDB + S3 (local API, AWS storage), **or**
   - `CAPACITY_BASE_URL` + contribution-ready token against deployed staging.  
   Current evidence:
   [`infra/capacity/evidence/2026-08-23-staging-remote-capacity.md`](../infra/capacity/evidence/2026-08-23-staging-remote-capacity.md)
   from the deployed AWS staging API (+ raw scenario, combined, and CloudWatch JSON siblings).
4. Review SLOs vs numbers; file critical defects; record operating limits and cost drivers.  
5. Confirm no unresolved **critical** capacity defects open against launch.

Do not confuse this with full #75 deployed smoke / rollback or multi-day soak tests.
