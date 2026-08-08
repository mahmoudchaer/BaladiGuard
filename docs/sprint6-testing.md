# Sprint 6 testing notes

Short index for Sprint 6 authorization, identity, and security verification.

## Primary artifacts

| Document | Purpose |
| --- | --- |
| [sprint6-role-permission-matrix.md](./sprint6-role-permission-matrix.md) | **Role-permission traceability matrix** (issue **#182**). Guest / citizen / municipal staff / administrator allowed vs rejected access, 401 vs 403 vs 404 rules, and links to automated tests or manual rows. |
| [MVP_API_CONTRACT.md](./MVP_API_CONTRACT.md) | Sprint 6 citizen identity, privacy, and staff route contracts. |
| [privacy-lifecycle.md](./privacy-lifecycle.md) | Account export/delete and session revocation expectations. |
| [sprint-plan.md](./sprint-plan.md) | Sprint 6 scope and issue wording alignment (#168–#178). |

## What #182 does **not** include

- Implementing missing authorization gates (tracked as matrix **gaps**).
- Expanding into an unbounded bugfix: failing Auto rows should open a focused defect on the owning feature ticket.

## Suggested CI / local focus set for auth

See the “How to re-run” section in the [role-permission matrix](./sprint6-role-permission-matrix.md).
