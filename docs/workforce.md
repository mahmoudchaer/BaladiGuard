# Municipality workforce directory (issue #245)

Field **workers** and **teams** are a municipality-scoped operational directory. They are **not** staff login accounts (`staff-users`). Workers do not authenticate; staff accounts assign them to tickets.

## Ownership

| Resource | Who writes | Who reads |
| --- | --- | --- |
| Worker / team directory | Administrators only | Authenticated staff in the same municipality |
| Team lead (`leadWorkerId`) | Administrators; must be a current team member | Same as directory |
| Ticket worker/team assignment | Municipal staff (own municipality + permitted department) and administrators | Same staff ticket read rules |
| Workload | Same as assignment | Counts only operational ticket fields |

Citizen contact, private photos, and tracking codes are never included on directory or workload payloads.

## Persistence

DynamoDB tables (prefix `baladiguard-` by default):

| Suffix | Key | GSI |
| --- | --- | --- |
| `workforce-workers` | `workerId` (`wrk_<hex>`) | `municipalityId-index` |
| `workforce-teams` | `teamId` (`team_<hex>`) | `municipalityId-index` |

Ticket attributes:

- `assignedWorkerId` / `assignedTeamId` — exclusive; both null means unassigned.
- Historical values stay on the ticket after a worker or team is deactivated. Deactivated records cannot receive **new** assignments.

## HTTP

- `GET/POST /v1/workforce/workers`, `PATCH /v1/workforce/workers/{id}`, `POST .../deactivate|reactivate`
- Same shape for `/v1/workforce/teams`
- `POST /v1/tickets/{id}/workforce-assignment` `{ workerId } XOR { teamId } XOR { clear: true }`
- `GET /v1/workforce/workload?municipalityId=`
- Drill-down: `GET /v1/tickets?workerId=` / `teamId=` / `workforceUnassigned=true` (separate from department `assignmentState`)

Assignment changes append ticket audit action `WORKFORCE_ASSIGN` with the authenticated `actorId` / `actorRole`.

Validate-then-write couples assignee eligibility with the ticket patch: memory
re-checks the worker/team under the same lock before writing the ticket; Dynamo
uses a `TransactWriteItems` that conditions the assignee on `active` (and
department) and the ticket on the municipality, department, and `updatedAt`
used for authorization. Clear uses the same ticket conditions. If the ticket
scope changed, the write fails, the ticket is reloaded, staff access and
assignment eligibility are re-run, then the commit retries. Deactivation or a
department/municipality change between those steps cannot create a new
assignment against a stale snapshot. Persistent conflicts return `409`.

## Workload counts

Active statuses: `SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`. `RESOLVED` and `CLOSED` are excluded.

- queued: `SUBMITTED` + `UNDER_REVIEW`
- assigned: `ASSIGNED`
- inProgress: `IN_PROGRESS`
- dueSoon / overdue: derived SLA (`derive_ticket_sla`); these can overlap status buckets
- completed: `RESOLVED` + `CLOSED` tickets assigned to that subject
- cancelled: `CLOSED` without `resolvedAt`

Dashboard aggregates use the same bucket definitions ([ticketing-lifecycle.md](./ticketing-lifecycle.md)).

Unassigned is the open-ticket bucket with no worker and no team. Team tickets are counted on the team row only, not copied onto member workers unless the ticket is assigned to that worker.

Workload paginates every ticket in the staff browse scope (page size 100). It does not use the dashboard aggregate sample cap, so drill-down lists match the counts.
