# Sprint 6 MVP acceptance & demo (issue #49)

Functional acceptance of the **complete Sprint 6 product flow** for local or stable
integration environments. Deployed hardening (security scans, capacity, DR, production
ops) is **out of scope** — see dedicated production-readiness issues.

## Purpose

Confirm citizens can sign up through tracking, and staff can log in through ticket ops,
with safe boundaries, mock notifications, and known limitations written down before the
sprint closes.

## Automated acceptance

Primary composite test (memory CI path):

```bash
cd backend
py -3.11 -m pytest tests/test_sprint6_mvp_flow_e2e.py -q
```

Broader supporting suites (role matrix + notifications + prior workflow):

```bash
py -3.11 -m pytest \
  tests/test_sprint6_mvp_flow_e2e.py \
  tests/test_sprint5_workflow_e2e.py \
  tests/test_staff_authorization.py \
  tests/test_citizen_otp_auth.py \
  tests/test_citizen_account.py \
  tests/test_citizen_privacy_lifecycle.py \
  tests/test_notifications.py \
  tests/test_submit_ticket.py \
  tests/test_merge_duplicate_tickets.py \
  tests/test_public_ticket_browsing.py \
  tests/test_upload_report_photo.py \
  -q
```

**Record (2026-08-09, issue #49):**

| Command | Result |
| --- | --- |
| `tests/test_sprint6_mvp_flow_e2e.py` | `1 passed` |
| Broader supporting suite (citizen + staff + merge + notifications + public + upload) | `157 passed` |

Role-permission matrix remains authoritative for Authed 401/403/404 rows:
[sprint6-role-permission-matrix.md](./sprint6-role-permission-matrix.md).

## Acceptance checklist

Tick during manual demo or after automated green run.

### Citizen account & session

| # | Check | Auto | Manual |
| --- | --- | --- | --- |
| C1 | OTP signup creates session + contribution-ready when full name provided | flow e2e | Mobile login |
| C2 | OTP login for existing account | `test_citizen_otp_auth` | Mobile |
| C3 | `GET /v1/citizen/me` restores profile with current token | flow e2e | Open app cold start |
| C4 | Profile patch (email / notification pref) | flow e2e | Profile screen |
| C5 | Logout revokes session; next `/me` is `401` | flow e2e | Logout control |
| C6 | Invalid/expired OTP, resend, rate limits | `test_citizen_otp_auth` | — |

### Citizen report & ownership

| # | Check | Auto | Manual |
| --- | --- | --- | --- |
| R1 | Contribution-ready submit links `ownerUserId` | flow e2e + submit tests | Submit real report |
| R2 | Guest / incomplete profile cannot submit (401 / 403) | flow e2e | Try without login |
| R3 | Photo upload requires contribution-ready session | `test_upload_report_photo` | Upload step |
| R4 | Validation rejects short description / missing image key | `test_submit_ticket` | Form validation UI |

### History, tracking, privacy

| # | Check | Auto | Manual |
| --- | --- | --- | --- |
| H1 | History empty page is `200` with `items: []` | flow e2e + privacy | Open History empty |
| H2 | History shows only owned tickets (tracking codes) | flow e2e + privacy | Two accounts |
| H3 | History never exposes contact / owner ids | flow e2e + privacy | Inspect network |
| H4 | Public track by code is citizen-safe (no PII) | flow e2e + tracking | Track screen |
| H5 | Public feed/browse does not expose private fields | `test_public_ticket_browsing` | Public list |

### Staff auth & ticket ops

| # | Check | Auto | Manual |
| --- | --- | --- | --- |
| S1 | Demo `admin` / `staff` login works | flow e2e + staff accounts | Admin login page |
| S2 | Unauthenticated staff routes → `401` | flow e2e + staff auth | Open dashboard logged out |
| S3 | Citizen token cannot access staff routes | flow e2e + staff auth | — |
| S4 | Staff list/detail review, department assign, status | flow e2e + sprint5 e2e | Detail actions |
| S5 | Merge duplicates within permitted rules | flow e2e + merge tests | Merge action |
| S6 | Municipal scope filters (Beirut roads/lighting demo staff) | `test_staff_authorization` | Log in as `staff` |
| S7 | Staff logout invalidates token | flow e2e | Logout |

### Notifications (local/test)

| # | Check | Auto | Manual |
| --- | --- | --- | --- |
| N1 | Profile `ticketUpdates` feeds recipient for mock adapter | flow e2e + notifications | Optional log tail |
| N2 | Status transitions emit mock `ticket_updated` without failing ticket write | flow e2e + notifications | Status change |
| N3 | Real SES/SNS only when `NOTIFICATION_ADAPTER=real` (sandbox first) | [notifications.md](./notifications.md) | Optional opt-in |

### UI states (loading / empty / validation / offline / server error)

Automated API coverage does **not** replace UI smoke. On **mobile** and **admin**, confirm:

| Surface | Loading | Empty | Validation | Offline / server error |
| --- | --- | --- | --- | --- |
| Mobile history | spinner/skeleton while fetching | empty message when no items | n/a | error banner when API down |
| Mobile track | lookup loading | invalid/miss code messaging | form validation | network error copy |
| Mobile report form | submit busy | — | field errors from API | fail-soft message |
| Admin ticket list | loading rows | empty queue | filter validation | session expired / 5xx toast |
| Admin login | busy button | — | bad password message | unreachable API |

How to simulate:

- Offline: OS airplane mode or stop the API process mid-flow  
- Server error: point client at wrong base URL or stop backend  

## Short demo path (recommended storyboard)

Total ~10–15 minutes on one machine.

1. **Env** — From repo root: `scripts/sync_env.py` (or local `.env`). Prefer `NOTIFICATION_ADAPTER=mock`. See [README](../README.md), [env-sync.md](./env-sync.md), [configuration.md](./configuration.md).
2. **Backend** — `uvicorn` on `:8000`; `GET /health` ok.
3. **Citizen (mobile)**  
   - OTP with a test phone (dev OTP via server logs / mock).  
   - Complete name if first login → become contribution-ready.  
   - Set email optionally; leave notification on SMS/mock.  
   - Submit a report with photo; copy tracking code.  
   - Open History; confirm only that report.  
   - Open Track with the code; timeline shows SUBMITTED.  
4. **Staff (admin)**  
   - Login `admin` / `DEMO_STAFF_PASSWORD` (default `staff-demo-password` local only).  
   - Open ticket; set category; assign department; move to UNDER_REVIEW then ASSIGNED.  
   - Refresh citizen Track → status advanced.  
   - (Optional) second similar ticket → merge.  
5. **Safety spot-check**  
   - Second phone account does **not** see first account’s history.  
   - Logged-out staff / citizen cannot open protected screens.  
6. **Stop** — Logout both sides; show re-login works.

Sample tickets (`SEED_SAMPLE_TICKETS` / `make db-seed --with-samples`) can fill the admin map/list for visual demos without citizen OTP.

## Known functional MVP limitations (Sprint 6 close)

Documented so #49 is not treated as an unbounded harden-everything ticket:

| Limitation | Notes / tracker |
| --- | --- |
| No admin HTTP staff-CRUD API | Service layer exists; no REST for create/deactivate staff in dashboard UI. [#236](https://github.com/mahmoudchaer/BaladiGuard/issues/236) |
| Admin vs municipal 404 pairing test still thin | Explicit paired Auto case tracked in [#235](https://github.com/mahmoudchaer/BaladiGuard/issues/235) |
| Notification ledger claim is process-local | Multi-worker exact once delivery is not a full distributed claim store yet. See [notifications.md](./notifications.md) |
| Real email/SMS needs SES/SNS setup | Default is mock; sandbox + allowlists required for safe real sends |
| Citizen OTP “SMS” in test/local is mock-friendly | Production OTP delivery path is separate from ticket notification SES/SNS |
| Guest photo upload blocked | Intended: contribution-ready only (#53) |
| Production observability / backup / DR | Separate Sprint tickets; not #49 functional acceptance |
| Full dual-backend browser E2E against live AWS | Not required for #49; memory CI + focused Dynamo moto tests remain |

## Failed scenarios

- **Fix in owning feature** if a regression appears in CI (auth #170/173, tickets, notifications, staff).  
- **Open a focused defect** if the gap is product backlog (link here and from the PR).  
- Do **not** expand #49 into production hardening or greenfield features.

## Related docs

| Doc | Role |
| --- | --- |
| [sprint6-testing.md](./sprint6-testing.md) | Index for #182 / #53 / #49 |
| [sprint6-role-permission-matrix.md](./sprint6-role-permission-matrix.md) | Auth matrix |
| [MVP_API_CONTRACT.md](./MVP_API_CONTRACT.md) | HTTP contract |
| [notifications.md](./notifications.md) | Delivery boundary |
| Root [README.md](../README.md) | Local MVP run + demo staff |
