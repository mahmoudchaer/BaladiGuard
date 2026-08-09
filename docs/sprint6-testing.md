# Sprint 6 testing notes

Short index for Sprint 6 authorization, identity, security, integration, and **full MVP flow acceptance**.

## Primary artifacts

| Document | Purpose |
| --- | --- |
| [sprint6-mvp-acceptance.md](./sprint6-mvp-acceptance.md) | **Issue #49** — full-flow checklist, demo path, UI-state smoke notes, known MVP limitations, automated acceptance command |
| [sprint6-role-permission-matrix.md](./sprint6-role-permission-matrix.md) | **Role-permission traceability matrix** (issue **#182**). Guest / citizen / municipal staff / administrator allowed vs rejected access, 401 vs 403 vs 404 rules, and links to automated tests or manual rows. |
| [MVP_API_CONTRACT.md](./MVP_API_CONTRACT.md) | Sprint 6 citizen identity, privacy, staff, ticket, upload, and location contracts. |
| [privacy-lifecycle.md](./privacy-lifecycle.md) | Account export/delete and session revocation expectations. |
| [api.md](./api.md) | API docs index (contract + OpenAPI entry points). |
| [sprint-plan.md](./sprint-plan.md) | Sprint 6 scope and issue wording alignment (#168–#178). |
| [notifications.md](./notifications.md) | Status-triggered delivery via the existing notification service (no separate notification HTTP API). |
| Root [README.md](../README.md) | Local MVP: `scripts/sync_env.py`, [configuration.md](./configuration.md), demo staff, migrate/seed. |

## Issue #49 — full MVP flow testing

| Check | How |
| --- | --- |
| End-to-end citizen → staff → track | `tests/test_sprint6_mvp_flow_e2e.py` |
| Checklist + demo path + limitations | [sprint6-mvp-acceptance.md](./sprint6-mvp-acceptance.md) |
| Focused auth rows | Matrix suite (#182) |
| Notifications | Mock path in flow e2e + `tests/test_notifications.py` |

```bash
cd backend
py -3.11 -m pytest tests/test_sprint6_mvp_flow_e2e.py -q
```

**Result (2026-08-09, issue #49):** composite MVP flow `1 passed`; broader supporting suite `157 passed`.

## Issue #53 — integration pass (bounded)

Re-verify that Sprint 6 account/auth work fits tickets, uploads, locations, notifications, and dual storage without rebuilding those foundations.

| Check | How |
| --- | --- |
| Role/permission matrix | Re-run suite in matrix “How to re-run” |
| Notifications | Existing `emit_ticket_notification` hooks + `tests/test_notifications.py` (no new endpoints) |
| Error envelope | Shared `{ error: { code, message, details, requestId } }` on public, citizen, staff, admin-gated paths |
| Memory + Dynamo | CI uses memory; Dynamo paths covered by focused moto/store tests where applicable |
| Upload gate | `POST /v1/uploads/report-photo` requires contribution-ready citizen (#53 closed **G-UPLOAD**) |
| Rate-limit codes | Domain OTP/reset and HTTP limits use `RATE_LIMIT_EXCEEDED` |

### Verification record (issue #53)

Run from `backend/` after changes on this ticket:

```bash
py -3.11 -m pytest tests/test_staff_authorization.py tests/test_staff_accounts.py tests/test_staff_password_reset.py tests/test_citizen_otp_auth.py tests/test_citizen_account.py tests/test_citizen_privacy_lifecycle.py tests/test_citizen_tracking_response.py tests/test_public_ticket_browsing.py tests/test_submit_ticket.py tests/test_upload_report_photo.py tests/test_report_submission_flow.py tests/test_notifications.py tests/test_sprint5_workflow_e2e.py tests/test_upload_abuse_early.py -q
```

**Result (2026-08-09, issue #53):** `180 passed` (1 Starlette deprecation warning only).

Remaining product-scope gaps:

- [#235](https://github.com/mahmoudchaer/BaladiGuard/issues/235) — **G-ADMIN-PAIR**
- [#236](https://github.com/mahmoudchaer/BaladiGuard/issues/236) — **G-ADMIN-HTTP**

## What these tickets do **not** include

- Greenfield re-implementation of unfinished account product features outside the integration boundary.
- Production security scanning, capacity, disaster recovery, or cloud harden-only work (other tickets).
- Expanding into an unbounded bugfix: failing Auto rows should open a focused defect on the owning feature ticket (or a scoped follow-up issue).

## Suggested CI / local focus set for auth

See the “How to re-run” section in the [role-permission matrix](./sprint6-role-permission-matrix.md).
