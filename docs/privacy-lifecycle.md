# Citizen data privacy lifecycle (MVP)

Authoritative MVP privacy lifecycle for issue #190, extended by issue #321
(legal package, consent, TTL, privacy-request audit). Aligns with the phone-first
identity contract in `docs/MVP_API_CONTRACT.md` (Sprint 6) and staff authorization
in issues #168 / #176.

**Legal package version:** `2026-08-22` (Terms, Privacy Policy, Acceptable Use) under
`docs/legal/{en,ar,fr}/`. These texts are product drafts for owner/legal counsel
review — not a GDPR/compliance certification. Contact: `privacy@baladiguard.app`.
Service intended for users **16+**. Controllers: BaladiGuard platform operator
(citizen accounts); participating municipalities (municipal ticket records).

Authoritative data-class inventory: `docs/data-inventory.md`.

## Legal documents and consent (#321)

| Surface | Behavior |
| --- | --- |
| Catalog | `GET /v1/legal` |
| Document body | `GET /v1/legal/{documentId}?lang=en\|ar\|fr` (fallback to `en`) |
| OTP verify (`LOGIN_OR_SIGNUP`) | Requires `acceptLegal: true`; persists `legalAcceptance` for the current package version |
| Profile | Exposes `legalAcceptance` and `legalAcceptanceRequired` (true when missing or version mismatch) |
| Re-accept | `POST /v1/citizen/me/legal-acceptance` |
| Account anonymize | Clears `legalAcceptance` |

### DynamoDB TTL (#321)

Migrations enable TTL attribute `ttl` on `citizen-sessions` and
`citizen-otp-challenges` (idempotent `_ensure_ttl`), matching the retention table
below.

## Citizen-facing privacy notice

BaladiGuard collects the minimum data needed to accept, route, and resolve municipal
infrastructure reports.

**What we collect**

| Data | Purpose |
| --- | --- |
| Verified phone number | Account identity, login (OTP), ticket ownership, SMS updates when enabled |
| Full name | Contribution readiness and optional public attribution when you enable it |
| Email (optional) | Ticket updates / announcements only when you choose email delivery |
| Notification preferences | How we contact you about your reports |
| Report content | Description, location, and photo needed to investigate and resolve the issue |
| Contact snapshot on each ticket | Immutable copy at submission for operational follow-up |
| Legal acceptance | Evidence you accepted the current Terms, Privacy Policy, and Acceptable Use |
| Session records | Keep you signed in and revoke access on logout, phone change, or deletion |
| Device / client metadata on submit | Abuse resistance and support diagnostics (not used for marketing) |

**What we do not do in the MVP**

- No citizen passwords
- No sale of personal data
- No real citizen data in automated tests, demo seeds, or shared fixtures
- No inventing SMS/email providers beyond the configured delivery adapters

**Your controls**

- View and update your profile (`GET` / `PATCH /v1/citizen/me`)
- Read current legal documents (`GET /v1/legal`, `GET /v1/legal/{documentId}`)
- Re-accept updated legal terms (`POST /v1/citizen/me/legal-acceptance`)
- Export a machine-readable copy of your account and owned tickets
  (`GET /v1/citizen/me/export`)
- Delete (anonymize) your account (`POST /v1/citizen/me/delete`)
- Turn off public name attribution (`publicNameVisible`, default `false`)

A short in-app summary ships in the mobile Privacy notice screen. The published
legal package lives under `docs/legal/`; this document describes lifecycle behavior.

## Retention periods

| Data class | Retention (MVP) | Notes |
| --- | --- | --- |
| Citizen accounts (active) | While the account remains active | Phone claim released on deletion |
| Citizen accounts (anonymized) | Retain tombstone row indefinitely for ownership / audit integrity | PII cleared; `active=false` |
| Tickets (municipal record) | Retain for municipal operations; target ≥ 7 years or until lawful disposal | Status, category, location, photo key, ownership id remain |
| Ticket contact snapshots | Retain with the ticket | Immutable submission-time contact for ops; not rewritten by profile edits |
| Report photos (S3) | Retain with the ticket; noncurrent versions 90 days | See `production-backup-restore.md` |
| Citizen sessions | Absolute 30-day TTL; revoked records may linger briefly then TTL purge | Logout / phone change / deletion revoke immediately |
| OTP challenges | 5-minute TTL; consumed/superseded records purge via TTL | Only keyed hashes stored |
| Password-reset records (staff) | Short-lived tokens per staff recovery design (#178) | Not citizen identity |
| Notifications / delivery ledger | Operational retention up to 90 days for delivery audit | Prefer ticket id over raw PII in logs |
| Ticket submission idempotency claims | Completed claim records ~14 days (DynamoDB TTL); unfinished reclaim window ~2 minutes | Retry safety only; not a municipal ledger |
| Ticket audit history | Retain with the ticket | Actor provenance for staff mutations |
| Application logs | 30–90 days in the log sink | No OTP codes; avoid logging full phone/email where possible |
| Analytics (admin dashboard) | Aggregates only | No citizen-identifying dimensions in MVP cards |
| Backups (DynamoDB PITR / S3 versions) | PITR window per AWS config; photo noncurrent 90 days | Restores are isolated; see backup runbook |
| Test / demo fixtures | Synthetic only; never production exports | `SEED_SAMPLE_TICKETS` / `SEED_DEMO_STAFF` off in production |

Exact calendar retention for municipal tickets may be extended by municipality policy
without changing the anonymization behavior below.

## Account deletion and anonymization

Citizens delete their account through `POST /v1/citizen/me/delete` (authenticated).

### What is removed or redacted on the citizen record

- Phone claim released so the number can be used by a new account
- Phone replaced with a non-login tombstone (`ANON:{userId}`)
- `fullName` and `email` cleared
- `legalAcceptance` cleared
- Notification preferences reset to `ticketUpdates=NONE`, `announcements=false`
- `publicNameVisible=false`
- `active=false`
- `sessionEpoch` incremented and all sessions revoked

### Municipal records that remain

| Record | Retained fields | Rationale |
| --- | --- | --- |
| Tickets | `ownerUserId`, status, category, location, description, photo key, municipality/department, AI/ops fields | Service continuity and lawful municipal record |
| Ticket `contact` snapshot | Submission-time name/phone/email/channel | Immutable ops/audit trail; not a live profile |
| Status / audit history | Prior staff actions and actor ids | Integrity of municipal workflow |
| Backups taken before deletion | Point-in-time copies until backup expiry | Disaster recovery; not used as a live directory |

Deletion must not rewrite ticket rows, break `ownerUserId` foreign references, or erase
audit history. Public attribution for owned tickets becomes `"Anonymous"` because the
owner is inactive / not publicly visible.

### After deletion

- Existing sessions return `401 UNAUTHORIZED`
- OTP login for the released phone creates a **new** account (new `userId`)
- The anonymized tombstone remains so historical tickets keep a stable owner key
- Export requires an active authenticated session (export before delete)

## Citizen data export

Implemented: `GET /v1/citizen/me/export` (citizen Bearer required).

Returns JSON with:

- `exportedAt`
- `profile` — same citizen-safe shape as `GET /v1/citizen/me`
- `tickets` — summary of tickets where `ownerUserId` equals the session user
  (ticket identifiers, status, category, description, location summary, timestamps)

Cross-user access is denied: another citizen's token cannot export this account.
Staff tokens receive `401` on citizen privacy routes (wrong audience), same as
`/v1/citizen/me`.

### Manual MVP fallback

If the export endpoint is unavailable in an environment, a privacy officer with
production read access may fulfill a verified request by:

1. Confirming the requester controls the account phone via a fresh OTP login or
   equivalent out-of-band municipal verification
2. Reading only that `userId`'s profile and owned tickets from the operational store
3. Delivering the JSON (or equivalent) over an access-controlled channel
4. Logging the request via developer ops:
   `POST /v1/ops/privacy-requests` (developer-operator auth), recording request id,
   action (`export` / `delete` / `manual_export` / `correction` / other),
   requester `userId` when known, fulfiller staff id, and timestamp

Citizen self-service export and delete also append privacy-request audit rows
automatically when those endpoints succeed.

No bulk export of unrelated citizens is permitted.

### Privacy request audit log (#321)

| Access | Path |
| --- | --- |
| Record (ops / manual) | `POST /v1/ops/privacy-requests` |
| List recent | `GET /v1/ops/privacy-requests` |
| Storage | Memory store in tests/local; DynamoDB table `privacy-request-audit` when enabled |

Self-service events use action types `citizen_export` and `citizen_delete`.

## Staff access to personal data

Staff may see ticket contact snapshots and related identity fields only through
staff-authenticated ticket routes, subject to the role and municipality/department
scope in the Sprint 6 authorization contract (#168 / #176).

- Citizens cannot read other citizens' profiles or exports
- Staff tokens cannot call citizen `/me`, export, or delete routes
- Mutation actor identity for ticket changes comes from the verified staff principal;
  client-supplied actor fields are not trusted
- Ticket mutations write auditable history (`auditHistory`)

Full department/municipality scoping completion remains with #176; this lifecycle
does not widen staff access.

## Logs, analytics, test data, and backups

| Surface | Rule |
| --- | --- |
| Logs | Never log OTP plaintext, access tokens, or password material. Prefer `userId` / `ticketId` over raw phone/email. |
| Analytics | Dashboard cards use aggregates only. |
| Tests / fixtures | Use synthetic phones, names, and emails (`example.com`). Do not copy production exports into the repo. |
| Demo seeds | `mock_tickets.json` and demo staff are synthetic; disable sample ticket seeding in production (`SEED_SAMPLE_TICKETS=false`). |
| Backups | Follow `docs/production-backup-restore.md`. Isolated restore targets only; never restore over live names. Backup copies expire with the configured PITR / version lifecycle. |

## Production / demo boundaries

- Production: `APP_ENV=production`, `SEED_SAMPLE_TICKETS=false`, `SEED_DEMO_STAFF=false`,
  non-demo secrets
- Local/test: synthetic fixtures and demo staff only
- CI must not require real citizen PII
- Mobile/admin mock layers must not embed production contact data

## Policy ownership and privacy request handling

| Role | Responsibility |
| --- | --- |
| Product / eng lead (BaladiGuard maintainers) | Own this document and the delete/export implementation |
| Municipality privacy contact | Receive formal citizen privacy requests for the deploying municipality |
| On-call / ops | Execute verified manual export or confirm automated deletion; keep request log |

### Handling a privacy request

1. Authenticate the requester (account session or municipal identity proof)
2. Classify: access/export, correction (profile PATCH), deletion, or staff inquiry
3. Prefer self-service export/delete endpoints when the citizen can authenticate
4. For manual cases, follow the fallback above and record: request id, date,
   requester `userId` or ticket reference, action taken, fulfiller staff id
5. Respond within the municipality's published SLA (MVP target: 30 calendar days)

Corrections to ticket contact snapshots are out of scope for self-service profile
edits (snapshots are immutable). Exceptional corrections require an audited staff
process defined by the municipality.

## Related documents

- `docs/legal/README.md` — legal package versioning and client loading
- `docs/data-inventory.md` — authoritative data-class inventory
- `docs/MVP_API_CONTRACT.md` — identity, privacy, and route contract
- `docs/database.md` — ownership vs contact snapshot
- `docs/production-backup-restore.md` — backup retention and restore isolation
- `docs/configuration.md` — production seed/secret boundaries
- `docs/notifications.md` — delivery behavior
