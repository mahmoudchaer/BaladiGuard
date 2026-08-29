# Municipal ticketing lifecycle and invariants (issue #318)

This is the authoritative join between ticket status, municipality ownership,
department, workforce assignment, work orders, SLA, evidence, and citizen
resolution feedback. Individual feature docs remain the detail source.

## Separate concepts

| Concept | Who owns it | Notes |
| --- | --- | --- |
| Staff account | Login + role/scope | Never auto-created for a worker |
| Worker / team | Operational assignee | No credentials; optional `leadWorkerId` on a team |
| Ticket status | Citizen-visible workflow | `SUBMITTED → UNDER_REVIEW → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED` |
| Municipality ownership | Routing / claim / reject | Independent of department |
| Department | Municipal work group | Required before `ASSIGNED` |
| Workforce assignment | Worker XOR team XOR clear | Historical IDs stay after deactivation |
| Work-order state | Field job | `QUEUED / ASSIGNED / IN_PROGRESS / COMPLETED / CANCELLED` |
| SLA | Derived, never stored | See [sla-policy.md](./sla-policy.md) |

## Required transitions

1. Developer operator provisions a municipality administrator (`POST /v1/ops/municipalities/{id}/admin`).
2. That administrator manages staff in their municipality only (cannot create `developer_operator`).
3. The same administrator manages workers/teams in that municipality.
4. A routed ticket is claimed, given a department, assigned to an eligible active worker/team, and optionally given a work order.
5. Work-order completion requires AFTER evidence and **does not** resolve the citizen ticket.
6. Resolution is an explicit staff status change. Citizen feedback can block `CLOSED` while review is pending.
7. `CLOSED` is rejected while an `activeWorkOrderId` remains (`ACTIVE_WORK_ORDER`).
8. Reopen is `RESOLVED → IN_PROGRESS` only.

## Cross-entity invariants

- Inactive, unknown, cross-municipality, or out-of-department workers/teams cannot receive **new** work.
- Stale `updatedAt` / expected state on ticket, worker, team, or work order returns `409` (never silent last-write-wins).
- Workload (`GET /v1/workforce/workload`) and dashboard aggregates (`GET /v1/tickets/aggregates`) use the same bucket function (`workload_buckets.py`) over the full staff scope.
- `unassignedCount` on aggregates remains “no department”. `workforceUnassignedCount` is “no worker and no team” on open tickets.
- `completed` = `RESOLVED` + `CLOSED`. `cancelled` = `CLOSED` with no `resolvedAt` (rejected / withdrawn without a citizen resolution).
- Assignment lineage is queryable at `GET /v1/tickets/{id}/assignment-history` (`DEPARTMENT_ASSIGN`, `WORKFORCE_ASSIGN`, `WORK_ORDER_ASSIGN`).
- Bounded bulk assign (`POST /v1/tickets/bulk/workforce-assignment` and `.../bulk/department`, max 25, optional `dryRun`) reuses the single-ticket mutators.

## Operating procedure

Queue, map, search, ticket workspace, workforce, and work orders all read the same persisted ticket. After a mutation, refresh or follow `freshnessHintSeconds` on list pages — consistency is near-real-time via reload, not a push bus.

See also [workforce.md](./workforce.md), [work-orders.md](./work-orders.md), [staff-accounts.md](./staff-accounts.md), [staff-comments-and-activity.md](./staff-comments-and-activity.md).
