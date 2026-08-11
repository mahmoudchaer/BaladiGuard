# Municipal service-level indicators

BaladiGuard shows staff-only decision-support indicators. They do not alter ticket status,
assignment, AI urgency, routing, or any citizen-facing promise.

## MVP policy (calendar hours)

| Urgency | Acknowledge | Resolve |
| --- | ---: | ---: |
| Low | 72 hours | 720 hours (30 days) |
| Medium | 48 hours | 336 hours (14 days) |
| High | 24 hours | 168 hours (7 days) |
| Critical | 4 hours | 48 hours |

The acknowledgement target applies while a ticket is `SUBMITTED`; later active statuses use the
resolution target. `RESOLVED` and `CLOSED` are `completed` rather than overdue. There is no paused
workflow state in the MVP; if one is introduced its clock policy must be defined before display.

All timestamps are parsed as timezone-aware ISO-8601 timestamps and compared in UTC. Legacy records
with a missing/invalid timestamp or no persisted urgency are `unavailable`, never guessed. A ticket
is `due_soon` during the final 20% of its active target and `overdue` only after its target instant.

Administrators may change policy values only through a reviewed deployment; the persisted ticket is
not mutated when policy calculations are displayed.
