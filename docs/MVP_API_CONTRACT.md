# BaladiGuard MVP API Contract

This document defines the initial MVP API contract for the mobile app and backend.

## Base API

| Item                 | Value |
| -------------------- | ----- |
| Base path            | `/v1` |
| Request body format  | JSON  |
| Response body format | JSON  |

## Headers

### Request headers

| Header                                |         Required | Description                                                                                                                        |
| ------------------------------------- | ---------------: | ---------------------------------------------------------------------------------------------------------------------------------- |
| `Content-Type: application/json`      |              Yes | Required for JSON request bodies.                                                                                                  |
| `Authorization: Bearer <accessToken>` | Protected routes | A citizen session token on citizen routes or a staff token on staff routes. Tokens are audience-bound and are not interchangeable. |
| `X-Client-Version`                    |               No | Optional client version, for example `mobile-0.1.0`.                                                                               |

### Response headers

| Header             | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `X-Request-Id`     | Request identifier returned by the backend for tracing errors.    |
| `WWW-Authenticate` | Present on `401 UNAUTHORIZED` authentication failures (`Bearer`). |

## Sprint 6 citizen identity and privacy contract

This section is the authoritative target contract for issues #168–#174, #178, #193, and #194.
It is a design contract: routes marked **planned** are not yet implemented. `POST /v1/tickets`
contribution-ready authentication is implemented by #173.

### Identity and contribution readiness

- A citizen's canonical identity is one verified phone number. `userId` is the stable internal
  ownership key; normalized phone is the unique login and reconciliation key.
- Citizen authentication is passwordless phone OTP. Citizen records and APIs must never accept,
  store, return, or recover a citizen password or password hash.
- Email is nullable secondary contact data for explicitly selected notifications, announcements,
  or receipts. It is not unique, a login identifier, an ownership key, or proof sufficient to
  recover an account after phone loss.
- A citizen is **contribution-ready** when the session is valid, the account is active, and
  `phoneVerifiedAt` is non-null for the account's current phone. Full name is optional profile
  data and is **not** required to contribute (#270). OTP verification for an inactive account
  returns `403 ACCOUNT_INACTIVE` without a session, while deactivation revokes existing sessions
  so their next use returns `401 UNAUTHORIZED`. An active account that is not contribution-ready
  (for example missing phone verification) receives `403 CONTRIBUTION_PROFILE_REQUIRED` on
  contribution routes.
- Guests may browse public data but may not create tickets or perform any other contribution.
  Clients must never supply `ownerUserId`; protected contribution routes derive it from the
  session.

### Canonical phone normalization

All creation, OTP, login, lookup, phone update, ticket linking, and future WhatsApp reconciliation
use the same E.164 canonical string: `+` followed by country calling code and national significant
number, with 8–15 digits total and no spaces or punctuation. Parse and validate with one pinned
libphonenumber-compatible implementation. The client must send either an E.164 number or a national
number plus an explicit ISO 3166-1 alpha-2 `region`; the server must not guess a region from locale,
IP address, or deployment. Formatting characters may be accepted as input but are removed only by
the parser, not by ad-hoc string replacement. Extensions, short codes, premium/service codes, and
numbers the parser does not classify as possible and valid are rejected.

Examples: `+961 70 123 456` and national `70 123 456` with `region: "LB"` both normalize to
`+96170123456`; Lebanese `03 123 456` with `region: "LB"` normalizes to `+9613123456` (the domestic
trunk `0` is not stored). The canonical value is never renormalized differently by a downstream
service.

### Citizen OTP and session routes

Implemented by issues #170 and #174 (account history at `GET /v1/citizen/me/tickets`).

| Route                               |                  Guest | Authenticated citizen | Contract                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------------------- | ---------------------: | --------------------: | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /v1/citizen/auth/otp/request` | `LOGIN_OR_SIGNUP` only |               Allowed | Accepts phone/region and purpose. `CHANGE_PHONE` requires a valid citizen session and applies only to that session's account; a guest request with that purpose returns `401`. Always returns `202` with a generic response after an authorized, valid request. A code is 6 digits, expires after 5 minutes, is single-use, stores only a keyed hash, and is bound to normalized phone, purpose, challenge ID, and—when changing phone—authenticated `userId`. At most 5 verification attempts are allowed; resend invalidates prior live codes. Per-phone, per-IP, per-account, and per-device throttles apply. |
| `POST /v1/citizen/auth/otp/verify`  | `LOGIN_OR_SIGNUP` only |               Allowed | Atomically consumes a valid challenge. `LOGIN_OR_SIGNUP` finds or creates the phone identity and returns an opaque citizen Bearer session. An inactive existing account returns `403 ACCOUNT_INACTIVE` after successful phone proof and no session is issued. `CHANGE_PHONE` requires the same authenticated citizen that requested the challenge. Responses before successful phone proof do not reveal whether the phone exists.                                                                                                                                                                               |
| `POST /v1/citizen/auth/logout`      |                     No |               Allowed | Immediately revokes the presented server-side session and returns `204`. Repeating with a revoked token returns `401`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `GET /v1/citizen/me`                |                     No |               Allowed | Returns the citizen-safe profile and `contributionReady`; never returns OTP material, internal claims, or credentials.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `PATCH /v1/citizen/me`              |                     No |               Allowed | Updates supported profile/preferences. A phone change requires a separately verified `CHANGE_PHONE` challenge and an atomic claim transfer. Email changes do not affect identity or sessions.                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `GET /v1/citizen/me/export`         |                     No |               Allowed | Returns a JSON export of the authenticated citizen's profile and owned-ticket summaries (`ownerUserId` match only). Staff tokens and other citizens receive `401` / cross-user denial. See `docs/privacy-lifecycle.md`.                                                                                                                                                                                                                                                                                                                                                                                          |
| `POST /v1/citizen/me/delete`        |                     No |               Allowed | Anonymizes the authenticated citizen account: releases the phone claim, redacts profile PII, sets `active=false`, bumps `sessionEpoch`, and revokes sessions. Returns `200` with deletion acknowledgement. Municipal ticket/audit rows remain. See `docs/privacy-lifecycle.md`.                                                                                                                                                                                                                                                                                                                                  |
| `GET /v1/citizen/me/tickets`        |                     No |               Allowed | Implemented account history; derives `userId` from the session and returns only citizen-safe summaries for tickets owned by it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

Citizen-safe profile shape for `GET` / `PATCH /v1/citizen/me` (issue #169):

```json
{
  "userId": "usr_…",
  "phone": "+96170123456",
  "phoneVerifiedAt": "2026-08-01T12:00:00Z",
  "fullName": "Ada Citizen",
  "email": null,
  "notificationPreferences": {
    "ticketUpdates": "NONE",
    "announcements": false
  },
  "publicNameVisible": false,
  "active": true,
  "contributionReady": true,
  "createdAt": "2026-08-01T12:00:00Z",
  "updatedAt": "2026-08-01T12:00:00Z"
}
```

`PATCH` accepts a partial body with any of `fullName`, `email` (nullable),
`notificationPreferences`, `publicNameVisible`, and—for phone changes—`phone`, optional
`region`, `phoneChangeChallengeId`, and `phoneChangeCode`. Phone changes revoke all sessions for
the account after the atomic claim transfer. Staff tokens on these routes return `401`.

Account deletion (`POST /v1/citizen/me/delete`) and export (`GET /v1/citizen/me/export`) follow the
privacy lifecycle in `docs/privacy-lifecycle.md`. Deletion keeps `ownerUserId` and immutable ticket
`contact` snapshots for municipal integrity while clearing live profile PII.

`GET /v1/citizen/me/tickets` returns the authenticated citizen's owned report history. It derives
the owner from the verified citizen session; clients cannot submit or override an owner id. Results
come from an owner-scoped storage query on `ownerUserId`, ordered by `createdAt` plus `ticketId`;
legacy unowned tickets are omitted, and public tracking remains a separate possession-based route.

Query parameters:

| Field    | Type    | Default | Bounds                    | Notes                                                         |
| -------- | ------- | ------: | ------------------------- | ------------------------------------------------------------- |
| `limit`  | integer |    `20` | `1`-`50`                  | Maximum page size.                                            |
| `cursor` | string  |  `null` | opaque continuation token | Opaque to clients except passing back the prior `nextCursor`. |

Successful response:

```json
{
  "items": [
    {
      "trackingCode": "AB23CD",
      "status": "IN_PROGRESS",
      "category": "road_damage",
      "locationAddress": "Near AUB Main Gate, Hamra, Beirut",
      "submittedAt": "2026-08-01T12:00:00Z"
    }
  ],
  "nextCursor": null,
  "limit": 20
}
```

Items are ordered newest first by `submittedAt`, with ticket id as a deterministic tie-breaker. The
history response never includes `ticketId`, `ownerUserId`, phone, email, contact snapshots, public
name preferences, OTP/session material, staff actors, department/municipality ids, audit history, or
AI/provider internals. Empty history returns `200` with an empty `items` array.

Minimal OTP payloads are fixed as follows:

- OTP request accepts `phone`, optional `region` (required for national-format input), and `purpose`.
  It returns `challengeId`, `expiresIn: 300`, and a generic `message`; it never returns the code.
- OTP verify accepts `challengeId`, `code`, and, for first-time `LOGIN_OR_SIGNUP`, optional
  `fullName`. It returns `accessToken`, `tokenType: "Bearer"`, `expiresIn: 2592000`, and the
  citizen-safe profile.
- `fullName` may be omitted during first verification. The new account is still contribution-ready
  when the phone is verified (#270); a name may be added later through `PATCH /v1/citizen/me`.

Successful OTP verification returns one cryptographically random, opaque Bearer access token. Only a
keyed hash is stored in the session record. The MVP session has an absolute 30-day lifetime, does not
slide on use, and has no refresh token. Each login creates a separately revocable session. Logout,
account deactivation, phone change, or an authorized administrative security action revokes affected
sessions immediately; expired and revoked records may be retained briefly for audit and then removed
by TTL. OTP verification does not revoke other sessions unless it changes the phone. Losing access to
a phone is not recoverable through email in the MVP; exceptional recovery requires a separately
approved design.

Malformed phone/challenge input returns `400 VALIDATION_ERROR`. OTP request throttling and exhausted
verification attempts return `429 RATE_LIMIT_EXCEEDED` (with `Retry-After` where known). An incorrect code
returns `400 INVALID_OTP`; an expired, consumed, or superseded challenge returns `400 OTP_EXPIRED`.
These responses are deliberately account-neutral. A successful verify consumes the challenge in the
same conditional operation that establishes its result so concurrent replay has at most one winner.

Missing, malformed, expired, revoked, logged-out, or wrong-audience credentials return `401
UNAUTHORIZED` with `WWW-Authenticate: Bearer`. A valid session lacking permission or contribution
readiness returns `403` without hiding public resources. Authentication and OTP errors are generic and
must not disclose account existence. Staff login, password storage, authorization, and password
recovery remain a separate staff-only contract; a staff token cannot authenticate a citizen route.

### Public browsing, attribution, and private contact

| Route                                   | Authentication             | Public/private rule                                                                                                                                          |
| --------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /v1/tickets/public`                | Public                     | Implemented citizen-safe list/map data with bounded pagination over explicitly published reports only.                                                       |
| `GET /v1/tickets/public/{ticketNumber}` | Public                     | Implemented citizen-safe report detail by public ticket number; unpublished reports return `404`.                                                            |
| `GET /v1/tickets/track/{trackingCode}`  | Public, possession-based   | Existing citizen-safe tracking response; tracking code is not account authentication.                                                                        |
| `POST /v1/locations/validate`           | Public                     | Guest-allowed draft assistance. It validates input but persists no report or contribution. Existing abuse controls still apply.                              |
| `POST /v1/uploads/report-photo`         | Contribution-ready citizen | Upload creates a persistent contribution artifact and is gated like ticket creation. Guests receive `401`. Verified-phone citizens may upload even without a full name (#270). |
| `POST /v1/tickets`                      | Contribution-ready citizen | Implemented by #173 / #270. Guests and revoked inactive-account sessions receive `401`. Verified-phone citizens may submit without a full name. |
| `/v1/staff/**` and staff ticket routes  | Authorized staff           | Identity/contact is returned only when the staff role and municipality/department scope authorize it.                                                        |

Public list, map, and detail responses expose exactly `ticketNumber`, public `status`, staff-reviewed
`category`, staff-approved `publicDescription` as `description`, coarse `publicLocationLabel` as
`location.addressText`, `mapLocation`, optional name-only `department`, `attribution`, optional
`photoUrl` (only when staff set `publicImageObjectKey`; never derived from the raw upload key),
`createdAt`, and `updatedAt`. A report is publishable only when `publicStatus` is `PUBLISHED`, a
final category is present, and both approved public text fields are non-empty; otherwise public list
omits it and public detail returns `404`. `mapLocation` contains the same coarse label plus latitude
and longitude rounded to 3 decimal places (about a 110 m latitude grid); it never contains the stored
`location.addressText`, stored location source, or exact coordinates. They must not expose
`ticketId`, `trackingCode`, `ownerUserId`, phone, email, contact snapshot, device metadata, internal
notes, staff actors, department/municipality IDs, duplicate internals, audit history, raw
descriptions, cleaned AI descriptions, raw `imageObjectKey`, or AI/provider internals. The
implementation must use a dedicated public projection and fail closed rather than serialize a staff
model.

Public browsing uses the `publicStatus-publicSortKey-index` storage query for stable keyset
pagination and the existing `ticketNumber-index` for detail lookup. The public mapper must not scan
all staff tickets or derive public copy from raw/cleaned descriptions at read time.

`attribution` is computed at read time. `attribution.displayName` is the citizen's current `fullName`
only when the ticket has an `ownerUserId`, that citizen is active, and their current
`publicNameVisible` is `true`; in that case `attribution.isNamed` is `true`. Otherwise
`displayName` is the literal `"Community member"` and `isNamed` is `false`. The default is `false`.
Changing the preference or name therefore affects every existing and future owned report
dynamically; turning visibility off hides all attribution immediately. A name is never copied into
the public projection, and legacy/unlinked tickets are always generic.

Ticket ownership and contact have different lifecycles. `ownerUserId` is the immutable stable owner.
`contact` is an immutable submission-time snapshot of the then-current normalized phone, optional
email, full name, and preferred notification channel. Later profile edits do not rewrite it. It is
visible solely to authorized staff; public attribution never reads `contact.name`.

The profile's `notificationPreferences.ticketUpdates` maps to the ticket's singular snapshot
`contact.preferredChannel` as follows: `SMS` → `SMS`, `EMAIL` → `EMAIL`, `BOTH` → `SMS` (MVP primary,
with email available as delivery fallback), and `NONE` → `null`. For account-linked tickets, actual
ticket create/status notification delivery uses the current owner profile preference at send time, so
later opt-out or channel changes apply without rewriting the snapshot. Legacy unowned tickets keep
using the immutable contact snapshot for delivery.

### Backward compatibility and linking

Tickets created before account enforcement remain valid, retain tracking-code access, and may keep
their legacy contact shape with `ownerUserId = null`; they are not rejected or rewritten and are
publicly anonymous. Contact phone/email alone never proves ownership. A later linking job or endpoint
may attach an unowned ticket only after the citizen verifies the normalized phone matching the
snapshot and supplies an additional ticket proof such as its tracking code. The conditional update
must require `ownerUserId` to be absent so linking cannot steal or reassign a ticket, and it must be
audited. Ambiguous/shared numbers and invalid legacy phones remain unlinked for manual review.

Future trusted WhatsApp ingestion must pass sender numbers through the same normalizer and atomic
phone claim. It may associate an existing `userId`, but it must not create a contribution-ready
citizen or mark a phone verified unless the separately approved WhatsApp verification policy provides
equivalent proof.

### Roles, permissions, and staff scope

The API recognizes three authorization roles. A citizen principal is identified by `userId` and a
citizen session. Staff principals use a separate staff identity and credential/session system.

| Role              | Identity and scope                                                                            | Allowed actions                                                                                                                                                                                                                |
| ----------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `citizen`         | Stable `userId`; no municipality/department authority.                                        | Public browsing and tracking; own profile/session/history; contribution-ready ticket and photo submission. A citizen can never read another citizen's profile/history or perform staff mutations.                              |
| `municipal_staff` | Staff identity scoped to one `municipalityId` and one or more assigned `departmentId` values. | Read and mutate tickets in that municipality and assigned departments, according to the route's action; view identity/contact only for authorized operational handling. No staff-account or cross-municipality administration. |
| `administrator`   | Staff identity with global municipality/department scope.                                     | All `municipal_staff` actions plus staff/role assignment, municipality and department administration, and cross-scope operational access.                                                                                      |

Route permissions are explicit:

| Route/action                                                                                                                       |                     Guest |                        Citizen |                            Municipal staff |                  Administrator |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------: | -----------------------------: | -----------------------------------------: | -----------------------------: |
| Public map/report list/detail and tracking lookup                                                                                  |                     Allow |                          Allow |                                      Allow |                          Allow |
| `POST /v1/locations/validate` draft validation                                                                                     |                     Allow |                          Allow |                                      Allow |                          Allow |
| OTP request/verify                                                                                                                 | Login/signup purpose only |       Own phone-change purpose |                                        N/A |                            N/A |
| Current profile, logout, and own history                                                                                           |                      Deny |                  Own resources |                                        N/A |                            N/A |
| `POST /v1/uploads/report-photo` and `POST /v1/tickets`                                                                             |                      Deny | Contribution-ready own session |                                        N/A |                            N/A |
| Staff ticket list/detail and all staff ticket mutations, including status/category/department/public actions and `POST /v1/tickets/merge` |                      Deny |                           Deny |                             Scoped tickets |                    All tickets |
| Staff identity/contact fields                                                                                                      |                      Deny |                           Deny | Authorized operational need and scope only | Authorized administrative need |
| Staff/role, municipality, and department administration                                                                            |                      Deny |                           Deny |                                       Deny |                          Allow |

Authentication is checked before authorization. Missing, malformed, expired, revoked, or wrong-audience
credentials return `401 UNAUTHORIZED`; a valid principal lacking the route permission returns `403
FORBIDDEN`. Citizen contribution failures retain the named `ACCOUNT_INACTIVE` and
`CONTRIBUTION_PROFILE_REQUIRED` codes defined above. Staff scope checks must be enforced server-side
from the staff session and stored role/scope, never from client-supplied `municipalityId`,
`departmentId`, or owner fields. For ticket resources, authorization occurs after loading the
resource, and a missing ticket or a ticket outside the caller's scope returns the identical `404
TICKET_NOT_FOUND` response. This prevents an ID probe from distinguishing nonexistent from
out-of-scope tickets. Non-resource permission failures continue to return `403 FORBIDDEN`.
Municipal staff may list and read unassigned tickets (`departmentId = null`) in their municipality
for triage; they may assign them only through the department-assignment action, after which normal
department scope applies. Administrator access is audited for identity/contact reads and
cross-municipality mutations.

## Staff authentication

Staff authenticate against individual persisted staff accounts (issue #175). Passwords are stored
only as PBKDF2 hashes and are never returned or logged. Login issues an HMAC-signed Bearer token
bound to `staffId` and `sessionEpoch`; logout and account deactivation increment `sessionEpoch` so
outstanding tokens fail on the next request. Shared env-credential login
(`STAFF_USERNAME` / `STAFF_PASSWORD` as the sole identity) has been removed. Local/test demos are
bootstrapped via `SEED_DEMO_STAFF` (see README / configuration docs). Citizen public browsing and
tracking stay public; citizen contribution uses the separate OTP-backed session contract.

Protected staff routes reject missing/invalid/expired/revoked tokens with `401` and code
`UNAUTHORIZED`, without leaking ticket contents or whether a ticket ID exists. Staff mutations
reuse the shared `require_staff` dependency.

## `POST /v1/staff/login`

Exchanges a staff username/password for a role-aware Bearer access token.
Shared HTTP rate limits apply (`staff-login`; default 10 / 300s). Exceeding the budget returns
`429 RATE_LIMIT_EXCEEDED` with `Retry-After` (see `docs/rate-limiting-runbook.md`).

### Request body

```json
{
  "username": "staff",
  "password": "staff-demo-password"
}
```

### Response `200`

```json
{
  "accessToken": "<signed-token>",
  "tokenType": "Bearer",
  "staffId": "staff_muni_001",
  "username": "staff",
  "name": "Demo Municipal Staff",
  "role": "municipal_staff",
  "municipalityId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "departmentIds": [
    "d1111111-1111-1111-1111-111111111111",
    "d3333333-3333-3333-3333-333333333333"
  ],
  "expiresIn": 43200
}
```

`role`, `municipalityId`, and `departmentIds` are server-derived authorization scope. Clients may
display them but cannot modify or use request-body copies to expand access. A municipal staff login
returns its assigned department IDs. A global administrator login returns exactly
`role: "administrator"`, `municipalityId: null`, and `departmentIds: null`; `null` is the explicit
all-departments sentinel and is never an empty assignment. Inactive accounts receive the same
generic `401 UNAUTHORIZED` as invalid credentials. Password hashes and credential metadata are
never included in the response.

## `POST /v1/staff/logout`

Requires a valid staff Bearer token. Immediately revokes outstanding tokens for that staff account
by incrementing `sessionEpoch` and returns `204`. Repeating with the revoked token returns `401`.

`N/A` in the permission matrix means that role is not a valid principal for that route. If a staff
token is presented to a citizen-only OTP/profile route, the wrong-audience authentication check
returns `401 UNAUTHORIZED` with `WWW-Authenticate: Bearer`; it is not treated as a guest request.

### Response `401`

Uses the common error format with `UNAUTHORIZED` when credentials are invalid.

## `POST /v1/staff/password-reset/request`

Staff-only password recovery (issue #178). Accepts a staff username and always returns the same
generic acknowledgement whether or not an active account exists. Does not return `challengeId`,
reset codes, or any existence signal. Shared HTTP rate limits apply
(`staff-password-reset-request`; same default budget as `staff-login`).

Citizens are passwordless under the OTP contract; there is no citizen forgot-password or reset
endpoint.

### Request body

```json
{
  "username": "staff"
}
```

### Response `200`

```json
{
  "message": "If a matching staff account exists, a password reset code has been issued."
}
```

Codes are stored only as HMAC hashes on `staff-password-reset-challenges` (15-minute TTL,
single-use, max 5 confirm attempts; a new request supersedes prior open challenges). In
`local` / `test` / `development`, plaintext codes are available only through the in-process
development peek adapter used by automated tests — never in HTTP responses. Production delivery
through email/SMS is out of scope for this ticket; the provider boundary may be wired later.

## `POST /v1/staff/password-reset/confirm`

Exchanges username + 6-digit code + new password for a successful reset. On success the staff
password hash is replaced with the same PBKDF2 scheme used at account creation, `sessionEpoch`
is incremented (all existing sessions revoked), and the challenge is consumed. Invalid, expired,
superseded, or reused codes return safe errors without revealing account existence.

Shared HTTP rate limits apply (`staff-password-reset-confirm`).

### Request body

```json
{
  "username": "staff",
  "code": "123456",
  "newPassword": "new-staff-password-123"
}
```

### Response `200`

```json
{
  "message": "Password updated. Sign in with your new password."
}
```

### Error codes

| HTTP  | Code            | When                                                                |
| ----- | --------------- | ------------------------------------------------------------------- |
| `400` | `RESET_INVALID` | Unknown username, wrong/consumed/superseded code, or inactive staff |
| `400` | `RESET_EXPIRED` | Code past TTL                                                       |
| `429` | `RATE_LIMIT_EXCEEDED` | Too many confirm attempts on the challenge (or shared HTTP limit)   |

## Staff audit boundaries (issues #143 / #181)

**Ticket audit (`auditHistory` on staff ticket responses)** covers status, category, department, public content,
and duplicate-merge mutations only. Entries store action type, target ticket, timestamp, summary,
previous/new values, plus verified `actorId` / `actorRole` from the authenticated principal.

**Account audit** is a separate store (`account-audit`) for Sprint 6 staff-account events:
create/role/scope/activation changes, password-reset completion, and session revoke/logout.
It is not exposed on ticket responses. Account-audit values never include passwords, hashes,
tokens, reset codes, or unnecessary citizen data. Write failures are logged and do not fail the
main account action.

Administrator account management is exposed only to `AdminStaffDep` through
`/v1/admin/staff-accounts`: list/read, create, role/scope update, and explicit
deactivate/reactivate operations. Responses exclude password hashes, reset-token
data, session epochs, and all credential values. The existing public staff
password-reset request/confirm endpoints remain the supported credential-reset
flow; administrators never receive reset codes or password material.

## Endpoints

## `GET /health/live`

Liveness probe. Returns `200` whenever the API process can answer. Does **not**
check DynamoDB, S3, or configuration. Use for container `HEALTHCHECK` / kube
liveness.

### Response `200`

```json
{
  "status": "live",
  "service": "baladiguard-api",
  "env": "local",
  "version": "0.1.0"
}
```

## `GET /health/ready`

Readiness probe for load balancers and deploy gates. Returns `200` when the
ticket store and configuration are OK; returns `503` with `"status": "not_ready"`
otherwise. AI queue depth may be included for operators but does **not** fail
readiness (backlog pages via metrics/alarms).

### Response `200` / `503`

```json
{
  "status": "ready",
  "service": "baladiguard-api",
  "env": "local",
  "version": "0.1.0",
  "database": {
    "backend": "memory",
    "status": "ok"
  },
  "config": {
    "status": "ok",
    "issues": []
  },
  "ai": {
    "status": "ok",
    "pending": 0,
    "processing": 0,
    "failed": 0,
    "source": "memory_store",
    "backlogWarnThreshold": 25
  }
}
```

## `GET /health`

Composite health for humans and demos. The process is considered up when this
endpoint responds with HTTP `200`. Inspect `status` and dependency fields for
`ok` / `degraded` / `error`. Deployment automation should prefer `/health/live`
and `/health/ready`.

### Response `200`

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local",
  "version": "0.1.0",
  "database": {
    "backend": "memory",
    "status": "ok"
  },
  "config": {
    "status": "ok",
    "issues": []
  },
  "ai": {
    "status": "ok",
    "pending": 0,
    "processing": 0,
    "failed": 0,
    "source": "memory_store",
    "backlogWarnThreshold": 25
  },
  "probes": {
    "liveness": "/health/live",
    "readiness": "/health/ready",
    "composite": "/health"
  }
}
```

When DynamoDB is configured and unreachable, `status` is `degraded` and
`database.status` is `error`, but `/health` still returns `200` so basic demos
keep working. `/health/ready` returns `503` in that case.

## `POST /v1/tickets`

Creates a submitted citizen report ticket.
Shared HTTP rate limits apply (`public-ticket-submission`; default 20 / 60s) because submit
triggers AI intake. Exceeding the budget returns `429 RATE_LIMIT_EXCEEDED` with `Retry-After`.

Optional idempotency (issue #258): send `Idempotency-Key: <key>` on the request (or body
`clientSubmissionId`). Replays with the same key and same owner return the original `201`
response body. A claim that is still in progress may return `409 SUBMISSION_IN_PROGRESS`.
Claims bind the created ticket id before finalizing the ledger entry and can be recovered
after a crash/`complete` failure; unfinished claims without a ticket become reclaimable after
~2 minutes. Keys without a valid shape are ignored (treated as non-idempotent submits).
Completed claim records are retained ~14 days (DynamoDB TTL attribute `ttl`) for offline retry
safety, then purged.

### Auth

Requires a contribution-ready citizen Bearer session (issues #173 / #270). The server derives
`ownerUserId` from that session and snapshots contact data from the citizen profile; client-supplied
ownership is forbidden. Missing authentication and revoked inactive-account sessions return `401`.
Verified-phone citizens may submit without a full name; `contact.name` may be null.

### Request body

```json
{
  "description": "Large pothole reported near the university gate causing traffic disruption.",
  "languageHint": "auto",
  "location": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "Near AUB Main Gate, Hamra, Beirut",
    "source": "PLACEHOLDER"
  },
  "imageObjectKey": "reports/mock/photo.jpg",
  "clientMetadata": {
    "platform": "ios",
    "appVersion": "0.1.0"
  }
}
```

### Request fields

| Field                       | Type   | Required | Notes                                                                                                                                                                                                                           |
| --------------------------- | ------ | -------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description`               | string |      Yes | Citizen description of the issue. Minimum 10 characters, maximum 2000 characters.                                                                                                                                               |
| `languageHint`              | string |       No | Use `auto` by default.                                                                                                                                                                                                          |
| `contact`                   | object |       No | Must be omitted. If supplied, the server returns `400 VALIDATION_ERROR`. Contact is snapshotted from the authenticated profile (`fullName` → `name`, verified phone, optional email, and `ticketUpdates` → `preferredChannel`). |
| `ownerUserId`               | string |       No | Must be omitted. If supplied, the server returns `400 VALIDATION_ERROR`. Ownership is derived from the verified citizen session.                                                                                                |
| `location`                  | object |      Yes | Report location.                                                                                                                                                                                                                |
| `location.latitude`         | number |      Yes | Finite latitude between `-90` and `90`, inclusive.                                                                                                                                                                              |
| `location.longitude`        | number |      Yes | Finite longitude between `-180` and `180`, inclusive.                                                                                                                                                                           |
| `location.addressText`      | string |      Yes | Trimmed readable address, landmark, or selected placeholder location text (3–500 characters).                                                                                                                                   |
| `location.source`           | enum   |      Yes | `GPS`, `MANUAL`, or `PLACEHOLDER`.                                                                                                                                                                                              |
| `imageObjectKey`            | string |      Yes | Stable image object key/reference used by the backend.                                                                                                                                                                          |
| `clientSubmissionId`        | string |       No | Optional client idempotency id (issue #258). Prefer the `Idempotency-Key` HTTP header. 8–128 characters matching `[A-Za-z0-9_-]`. Scoped per citizen; retries return the original success payload without creating a second ticket. |
| `clientMetadata`            | object |      Yes | Client metadata sent by the mobile app.                                                                                                                                                                                         |
| `clientMetadata.platform`   | string |      Yes | Example values: `ios`, `android`, `web`.                                                                                                                                                                                        |
| `clientMetadata.appVersion` | string |      Yes | Mobile app version.                                                                                                                                                                                                             |

### Response `201`

```json
{
  "ticketId": "tkt_2f7b3a5e4c9d4a0c9c1b8f1234567890",
  "ticketNumber": "BG-2026-0001",
  "trackingCode": "AB23CD",
  "status": "SUBMITTED",
  "message": "Your report was submitted successfully.",
  "createdAt": "2026-07-03T00:54:15Z"
}
```

### Response fields

| Field          | Type   | Notes                                |
| -------------- | ------ | ------------------------------------ |
| `ticketId`     | string | Internal ticket identifier.          |
| `ticketNumber` | string | Citizen-facing ticket number.        |
| `trackingCode` | string | Citizen-facing tracking code.        |
| `status`       | enum   | Initial value is `SUBMITTED`.        |
| `message`      | string | Human-readable confirmation message. |
| `createdAt`    | string | ISO 8601 timestamp.                  |

## `GET /v1/tickets/track/{trackingCode}`

Looks up a citizen report by its tracking code and returns the public tracking contract.
This endpoint must use `CitizenTicketResponse`; it must not return `TicketResponse` and rely on
frontend field hiding.

### Response `200`

```json
{
  "ticketNumber": "BG-2026-0001",
  "trackingCode": "AB23CD",
  "status": "IN_PROGRESS",
  "category": "road_damage",
  "location": {
    "addressText": "Near AUB Main Gate, Hamra, Beirut"
  },
  "department": {
    "name": "Road Maintenance"
  },
  "createdAt": "2026-08-12T09:30:00Z",
  "updatedAt": "2026-08-12T11:30:00Z",
  "lastUpdatedAt": "2026-08-12T11:30:00Z",
  "timeline": [
    {
      "status": "SUBMITTED",
      "changedAt": "2026-08-12T09:30:00Z"
    },
    {
      "status": "IN_PROGRESS",
      "changedAt": "2026-08-12T11:30:00Z"
    }
  ]
}
```

### Public response fields

| Field                  | Type           | Notes                                                                                                                                      |
| ---------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `ticketNumber`         | string or null | Citizen-facing ticket number when available.                                                                                               |
| `trackingCode`         | string         | Citizen-facing tracking code entered by the resident.                                                                                      |
| `status`               | `TicketStatus` | Current public workflow status.                                                                                                            |
| `category`             | string or null | Staff-approved/current public category when available; omitted as null while classification is pending or unapproved.                      |
| `location.addressText` | string         | Public-readable location text only. Coordinates and location source remain staff-only.                                                     |
| `department.name`      | string         | Name-only assigned department display when status is `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, or `CLOSED`; otherwise `department` is `null`. |
| `createdAt`            | string         | ISO 8601 timestamp for original submission.                                                                                                |
| `updatedAt`            | string or null | ISO 8601 timestamp for the latest ticket update when available.                                                                            |
| `lastUpdatedAt`        | string         | `updatedAt` when present, otherwise `createdAt`, for citizen tracking display.                                                             |
| `timeline[].status`    | `TicketStatus` | Public status reached at this point in the workflow.                                                                                       |
| `timeline[].changedAt` | string         | ISO 8601 timestamp for the status change.                                                                                                  |

### Staff-only fields excluded from citizen tracking

Citizen tracking responses must not include internal ticket IDs, contact details, photo storage
references, department identifiers, staff actor IDs, municipality IDs, duplicate group data, internal
status notes, authorization data, staff-only controls, or AI/provider implementation details. A
citizen response may include a name-only `department` display after assignment, but the internal
department ID remains staff-only. These fields remain available only through staff `TicketResponse`
endpoints where appropriate.

### Auth

Public. No staff authentication is required.

### Client lookup path (issue #37)

Mobile (and any citizen client) must call this public endpoint **directly** after trimming and
validating the tracking code on the client. The backend is the only approved resolver (memory or
DynamoDB lookup by `trackingCode`). Citizens must **not** use staff
`GET /v1/tickets/{ticketId}` or invent an alternate lookup path.

Client-side validation expectations before the request:

- Reject empty / whitespace-only input without calling the API.
- Trim and uppercase the code, then require the tracking-code format below.
- On `404`, show a clear non-sensitive not-found message (do not leak internal IDs or staff fields).
- Disable submit while a lookup is in flight so repeated taps do not create duplicate requests.

### Tracking code format

Citizen tracking codes are 6 characters drawn from `A-Z` and `2-9`, excluding ambiguous characters
`I`, `O`, `0`, and `1`. Lookups are case-insensitive.

### Tracking lookup error codes

| Code               | Status | Meaning                                                         |
| ------------------ | -----: | --------------------------------------------------------------- |
| `VALIDATION_ERROR` |    400 | The tracking code format is invalid (wrong length or alphabet). |
| `TICKET_NOT_FOUND` |    404 | No ticket exists for a well-formed tracking code.               |

## `GET /v1/tickets`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Returns a **lightweight paginated collection** (`TicketListPageResponse`), sorted by
`createdAt` / `ticketId` descending via indexed staff GSIs (issue #267). Items do **not**
include contact, tracking codes, status/audit history, image URLs, or AI/public blobs.
Full detail remains on `GET /v1/tickets/{ticketId}`. See
[staff-ticket-collection.md](./staff-ticket-collection.md).

Optional query filters match **persisted** ticket fields and are combined with AND.
`slaState` is derived (not indexed); the service continues fetching bounded source pages
until the filtered page is filled or the source is exhausted. Omitting a
parameter leaves that dimension unfiltered. An empty match set returns
`{ "items": [], ... }` (HTTP 200), not an error.

### Query Parameters

| Name           | Type   | Required | Description                                                                                                                                                                 |
| -------------- | ------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status`       | enum   | No       | Exact match on ticket `status`. One of `SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`.                                                        |
| `category`     | string | No       | Exact match on ticket `category` (including `PENDING_CLASSIFICATION`). Must be a seeded catalog category ID.                                                                |
| `urgency`      | enum   | No       | Exact match on persisted urgency level stored as ticket `priority`. One of `low`, `medium`, `high`, `critical`. Tickets with `priority: null` do not match.                 |
| `departmentId` | string | No       | Exact match on assigned `departmentId` (staff override or automatic assignment). Must be a seeded department catalog ID. Does **not** filter on `ai.suggestedDepartmentId`. |
| `slaState`     | enum   | No       | Derived SLA filter with bounded continue-fetch: `on_track`, `due_soon`, `overdue`, `completed`, `unavailable`.                                                              |
| `limit`        | int    | No       | Page size (default 25, max 100).                                                                                                                                            |
| `cursor`       | string | No       | Opaque continuation cursor from a prior `nextCursor`.                                                                                                                       |

Invalid or blank filter values / cursors return `400` with `error.code = VALIDATION_ERROR`.

### Response `200`

```json
{
  "items": [
    {
      "ticketId": "tkt_2f7b3a5e4c9d4a0c9c1b8f1234567890",
      "ticketNumber": "BG-2026-0001",
      "status": "SUBMITTED",
      "category": "PENDING_CLASSIFICATION",
      "priority": null,
      "departmentId": null,
      "department": null,
      "summary": "Large pothole reported near the university gate causing traffic disruption.",
      "createdAt": "2026-07-03T00:54:15Z",
      "updatedAt": "2026-07-03T00:54:15Z",
      "municipalityId": null,
      "assignmentState": "unassigned",
      "location": {
        "latitude": 33.896112,
        "longitude": 35.478419,
        "addressText": "Near AUB Main Gate, Hamra, Beirut"
      }
    }
  ],
  "nextCursor": null,
  "previousCursor": null,
  "limit": 25,
  "scannedCount": 1,
  "approximateTotal": null,
  "freshnessHintSeconds": 30
}
```

## `GET /v1/tickets/map`

Staff-only. Viewport-bounded map contract (issue #267). Query: `north`, `south`, `east`,
`west`, `zoom`, optional collection filters, `limit` (default 200, max 500). Returns
`markers` and/or `clusters` with `truncated` when the candidate budget is exhausted.

## `GET /v1/tickets/aggregates`

Staff-only. Scoped attention counts (`openCount`, `criticalCount`, `highCount`,
`unassignedCount`, `overdueCount`) with `approximate` when sampled.

## `GET /v1/tickets/{ticketId}`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Returns one persisted ticket by ID using the ticket record shape.

### Response `200`

```json
{
  "ticketId": "tkt_2f7b3a5e4c9d4a0c9c1b8f1234567890",
  "ticketNumber": "BG-2026-0001",
  "trackingCode": "AB23CD",
  "description": "Large pothole reported near the university gate causing traffic disruption.",
  "contact": {
    "name": "Citizen Name",
    "phone": "+96170123456",
    "email": "citizen@example.com"
  },
  "location": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "Near AUB Main Gate, Hamra, Beirut",
    "source": "PLACEHOLDER"
  },
  "imageReferences": [
    {
      "objectKey": "reports/mock/photo.jpg",
      "url": null,
      "contentType": null,
      "createdAt": null
    }
  ],
  "imageObjectKey": "reports/mock/photo.jpg",
  "status": "SUBMITTED",
  "category": "PENDING_CLASSIFICATION",
  "priority": null,
  "department": null,
  "createdBy": null,
  "municipalityId": null,
  "departmentId": null,
  "duplicateGroupId": null,
  "createdAt": "2026-07-03T00:54:15Z",
  "updatedAt": "2026-07-03T00:54:15Z"
}
```

### Response `404`

Uses the common error format with `TICKET_NOT_FOUND`.

Unauthenticated staff reads return `401` with `UNAUTHORIZED` and do not reveal whether the ticket
exists.

## `PATCH /v1/tickets/{ticketId}/status`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Updates a ticket's workflow status using the strict transition rules documented below.

### Request body

```json
{
  "status": "UNDER_REVIEW",
  "updatedBy": "staff-1",
  "note": "Queued for review."
}
```

### Request fields

| Field       | Type           | Required | Notes                                                                                                   |
| ----------- | -------------- | -------: | ------------------------------------------------------------------------------------------------------- |
| `status`    | `TicketStatus` |      Yes | Target status. Invalid enum values are rejected with `400` (`VALIDATION_ERROR`).                        |
| `updatedBy` | string         |       No | Ignored for trust decisions; audit/history actor identity is derived from the verified staff principal. |
| `note`      | string         |       No | Optional human-readable note (max 500 characters).                                                      |

### Response `200`

Returns the updated `TicketResponse`, including `updatedAt`, `updatedBy`, `statusHistory`, and
`auditHistory` (staff audit complements status history).

### Status update error codes

| Code                        | Status | Meaning                                                           |
| --------------------------- | -----: | ----------------------------------------------------------------- |
| `UNAUTHORIZED`              |    401 | Missing, invalid, or expired staff Bearer token.                  |
| `TICKET_NOT_FOUND`          |    404 | Ticket ID does not exist.                                         |
| `INVALID_STATUS_TRANSITION` |    400 | Requested status is not allowed from the ticket's current status. |

## `PATCH /v1/tickets/{ticketId}/category`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Records the staff-approved final category without overwriting the original AI suggestion or
explanation.

### Request body

```json
{
  "finalCategory": "road_damage",
  "categoryReviewedBy": "staff-1"
}
```

| Field                | Type   | Required | Notes                                                                                        |
| -------------------- | ------ | -------: | -------------------------------------------------------------------------------------------- |
| `finalCategory`      | string |      Yes | One concrete supported category ID. `PENDING_CLASSIFICATION` is not a final category.        |
| `categoryReviewedBy` | string |       No | Ignored for trust decisions; reviewer identity is derived from the verified staff principal. |

### Response `200`

Returns the updated `TicketResponse`. The top-level `category` and `ai.finalCategory` contain the
approved category. `ai.categoryReviewedAt` is generated by the server, and
`ai.aiSuggestedCategory` remains unchanged. Staff responses also append a `CATEGORY_REVIEW` entry
to `auditHistory`.

### Category review error codes

| Code               | Status | Meaning                                                                                      |
| ------------------ | -----: | -------------------------------------------------------------------------------------------- |
| `UNAUTHORIZED`     |    401 | Missing, invalid, or expired staff Bearer token.                                             |
| `TICKET_NOT_FOUND` |    404 | Ticket ID does not exist.                                                                    |
| `FORBIDDEN`        |    403 | Authenticated staff principal cannot assign the department implied by the reviewed category. |
| `VALIDATION_ERROR` |    400 | The category is missing, pending, or not in the supported category catalog.                  |

## `PATCH /v1/tickets/{ticketId}/public`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Sets the staff-approved public projection used by guest browsing. Raw citizen description and the
exact stored address are never copied automatically. Public photos require an explicit approval of
**this ticket's** private upload via `approveOriginalPhoto` (server copies `imageObjectKey` into
`publicImageObjectKey`). `clearPublicPhoto` removes the public photo. Caller-supplied object keys
are rejected — alternate/redacted keys are deferred until a ticket-bound upload/artifact record
exists. Omitting both approve and clear leaves any existing public photo unchanged. Publishability
still requires `publicStatus=PUBLISHED`, a staff-reviewed final category, and non-empty public
description + coarse location label; the photo is optional.

### Request body

```json
{
  "publicStatus": "PUBLISHED",
  "publicDescription": "Staff-approved public summary of the road hazard.",
  "publicLocationLabel": "Hamra, Beirut",
  "approveOriginalPhoto": true
}
```

| Field                   | Type    | Required | Notes                                                                                         |
| ----------------------- | ------- | -------: | --------------------------------------------------------------------------------------------- |
| `publicStatus`          | string  |      Yes | `DRAFT`, `PUBLISHED`, or `UNPUBLISHED`.                                                       |
| `publicDescription`     | string  |      Yes | Required non-empty when publishing.                                                           |
| `publicLocationLabel`   | string  |      Yes | Coarse neighborhood/area label; required non-empty when publishing.                           |
| `approveOriginalPhoto`  | boolean |       No | When `true`, copies this ticket's private `imageObjectKey` into `publicImageObjectKey`.       |
| `clearPublicPhoto`      | boolean |       No | When `true`, clears `publicImageObjectKey`. Mutually exclusive with approve.                  |
| `updatedBy`             | string  |       No | Ignored for trust decisions; actor identity comes from the verified staff principal.          |

### Response `200`

Returns the updated `TicketResponse`, including a staff-only `public` object with
`status`, `description`, `locationLabel`, `imageObjectKey`, and `publishedAt`. Staff responses also
append a `PUBLIC_CONTENT_UPDATE` entry to `auditHistory`.

### Public content error codes

| Code               | Status | Meaning                                                                                 |
| ------------------ | -----: | --------------------------------------------------------------------------------------- |
| `UNAUTHORIZED`     |    401 | Missing, invalid, or expired staff Bearer token.                                        |
| `TICKET_NOT_FOUND` |    404 | Ticket ID does not exist (or is outside the staff principal's scope).                   |
| `VALIDATION_ERROR` |    400 | Missing final category/public text when publishing, conflicting photo-mode flags, or unknown fields (including caller-supplied `publicImageObjectKey`). |

## `PATCH /v1/tickets/{ticketId}/department`

Staff-only (authorization via the shared staff dependency integration point for issue #72).
Assigns or overrides the ticket department from the seeded department catalog without clearing the
automatic department suggestion.

### Request body

```json
{
  "departmentId": "d2222222-2222-2222-2222-222222222222",
  "updatedBy": "staff-1"
}
```

| Field          | Type   | Required | Notes                                                                                           |
| -------------- | ------ | -------: | ----------------------------------------------------------------------------------------------- |
| `departmentId` | string |      Yes | Must be one of the seeded department catalog IDs.                                               |
| `updatedBy`    | string |       No | Ignored for trust decisions; audit actor identity is derived from the verified staff principal. |

### Response `200`

Returns the updated `TicketResponse`. Top-level `department` / `departmentId` reflect the staff
assignment. `ai.suggestedDepartmentId` keeps the original automatic suggestion when present.
Staff responses also append a `DEPARTMENT_ASSIGN` entry to `auditHistory`.

### Department assignment error codes

| Code               | Status | Meaning                                                               |
| ------------------ | -----: | --------------------------------------------------------------------- |
| `TICKET_NOT_FOUND` |    404 | Ticket ID does not exist.                                             |
| `VALIDATION_ERROR` |    400 | The department ID is missing or not in the seeded department catalog. |
| `UNAUTHORIZED`     |    401 | Missing/invalid staff auth once issue #72 is wired.                   |
| `FORBIDDEN`        |    403 | Authenticated staff principal cannot assign the requested department. |

## `GET /v1/tickets/{ticketId}/duplicate-candidates`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Dedicated merge-candidate search for one ticket (issue #269). The admin duplicate workspace
uses it instead of scanning a single `GET /v1/tickets` page, so a valid candidate is never
hidden behind list pagination or an unrelated dashboard filter.

### Query Parameters

| Name     | Type   |                Default | Notes                                                                    |
| -------- | ------ | ---------------------: | ------------------------------------------------------------------------ |
| `q`      | string |                   none | Case-insensitive match on ticket number, description, and address text. |
| `limit`  | int    |                     20 | Page size, max 50.                                                       |
| `cursor` | string |                   none | Opaque continuation cursor from a previous `nextCursor`.                  |

### Candidate rules

- The source ticket must be visible to the caller under the same staff scope as
  `GET /v1/tickets/{ticketId}`; otherwise `404 TICKET_NOT_FOUND`.
- The source ticket must already be classified. An unclassified source has no effective
  category to match, so the response is an empty page.
- Returned tickets always exclude the source itself, exclude tickets that already belong to a
  duplicate group, keep only open statuses (`SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`,
  `IN_PROGRESS`), and share the source's **effective category** (`finalCategory`, else
  `aiSuggestedCategory`, else the stored category) — the same semantics
  `POST /v1/tickets/merge` enforces.
- Because the effective category is derived rather than persisted, the service keeps pulling
  staff list pages until the requested page size is filled or the scan ends. `nextCursor` is
  the continuation for the *underlying list scan*, so a page can be short and still have more.
- Every returned row satisfies the merge preconditions the API can check up front, hence
  `mergeable: true`.

### Response `200`

```json
{
  "items": [
    {
      "ticketId": "tkt_55555555555555555555555555555555",
      "ticketNumber": "BG-2026-0201",
      "status": "SUBMITTED",
      "category": "road_damage",
      "priority": "high",
      "summary": "Deep pothole opposite the campus entrance.",
      "createdAt": "2026-07-17T07:30:00Z",
      "location": {
        "latitude": 33.8965,
        "longitude": 35.4782,
        "addressText": "Bliss Street, Beirut"
      },
      "distanceMeters": 42.4,
      "imageUrl": "https://s3.example/presigned/...",
      "suggested": true,
      "score": 0.82,
      "categoryMatch": "same",
      "mergeable": true
    }
  ],
  "nextCursor": "eyJ0aWNrZXRJZCI6...",
  "limit": 20
}
```

| Field            | Type    | Notes                                                                                    |
| ---------------- | ------- | ---------------------------------------------------------------------------------------- |
| `summary`        | string  | Bounded description excerpt, same shape as staff list items.                              |
| `distanceMeters` | number? | Great-circle distance from the source ticket; omitted when either location is unusable.  |
| `imageUrl`       | string? | Short-lived presigned GET URL. The raw `imageObjectKey` is never returned.                |
| `suggested`      | bool    | `true` when the automated detector also flagged this pair for the source ticket.          |
| `score`          | number? | Detector confidence, present only for suggested rows.                                     |
| `categoryMatch`  | string? | `same` or `similar`, present only for suggested rows.                                     |
| `mergeable`      | bool    | Always `true`; the endpoint filters out rows the merge mutation would reject.              |

This projection deliberately omits `contact`, `trackingCode`, `imageObjectKey`, `auditHistory`,
`statusHistory`, AI blobs, and public-content drafts: choosing duplicates needs evidence, not
citizen identity.

### Duplicate candidate error codes

| Code               | Status | Meaning                                                       |
| ------------------ | -----: | ------------------------------------------------------------- |
| `UNAUTHORIZED`     |    401 | Missing, invalid, or expired staff Bearer token.              |
| `TICKET_NOT_FOUND` |    404 | Source ticket does not exist or is outside the staff scope.   |
| `VALIDATION_ERROR` |    400 | `cursor` is malformed, or `limit` is outside `1..50`.         |

## `GET /v1/tickets/{ticketId}/duplicate-comparison/{candidateTicketId}`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Bounded side-by-side projection of one candidate for the merge review (issue #269). The admin
comparison panel reads this instead of `GET /v1/tickets/{candidateTicketId}`, so reviewing a
possible duplicate never pulls another citizen's full record into the browser.

Both the source and the candidate ticket must be visible to the caller under the staff list
scope; either miss returns `404 TICKET_NOT_FOUND`.

### Response `200`

```json
{
  "ticketId": "tkt_55555555555555555555555555555555",
  "ticketNumber": "BG-2026-0201",
  "description": "Second report about the same pothole.",
  "status": "SUBMITTED",
  "category": "road_damage",
  "priority": "high",
  "createdAt": "2026-07-17T07:30:00Z",
  "location": {
    "latitude": 33.8965,
    "longitude": 35.4782,
    "addressText": "Bliss Street, Beirut"
  },
  "imageUrl": "https://s3.example/presigned/...",
  "distanceMeters": 42.4
}
```

`category` is the effective category. `distanceMeters` is measured against the source ticket.
`imageUrl` is a presigned GET URL only. The response omits `contact`, `trackingCode`,
`imageObjectKey`, `auditHistory`, `statusHistory`, AI fields, public-content drafts, and
`createdBy`/owner identity.

### Duplicate comparison error codes

| Code               | Status | Meaning                                                                        |
| ------------------ | -----: | ------------------------------------------------------------------------------ |
| `UNAUTHORIZED`     |    401 | Missing, invalid, or expired staff Bearer token.                               |
| `TICKET_NOT_FOUND` |    404 | Source or candidate ticket does not exist or is outside the staff scope.       |

## `POST /v1/tickets/merge`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Links one or more duplicate tickets under a staff-chosen main ticket and persists a
`DuplicateGroup`.

### Request body

```json
{
  "canonicalTicketId": "tkt_22222222222222222222222222222222",
  "duplicateTicketIds": ["tkt_55555555555555555555555555555555"],
  "mergedBy": "staff-1"
}
```

| Field                | Type     | Required | Notes                                                                                           |
| -------------------- | -------- | -------: | ----------------------------------------------------------------------------------------------- |
| `canonicalTicketId`  | string   |      Yes | Main ticket that remains the group representative.                                              |
| `duplicateTicketIds` | string[] |      Yes | One or more other ticket IDs to link. Must not include the main ticket.                         |
| `mergedBy`           | string   |       No | Ignored for trust decisions; merge actor identity is derived from the verified staff principal. |

### Merge rules

- Every ticket (main and duplicates) must share the same **effective category**: the
  staff-reviewed `finalCategory`, else the AI `aiSuggestedCategory`, else the stored
  category when already classified. Tickets still pending classification cannot be merged.
- Duplicate tickets must not already belong to a duplicate group. Regrouping or
  unlinking existing members is rejected instead of silently shattering groups.
- If the main ticket already leads a group, the new duplicates are **appended** to that
  existing group (same `duplicateGroupId`, extended `ticketIds`). Merging from a
  non-main group member is rejected with a message pointing at the main ticket.
- Member tickets are stamped before the group row is saved; on failure the stamps are
  rolled back so no `DuplicateGroup` row is left pointing at unstamped tickets.
- Unmerge / leave-group is intentionally **out of scope** for issue #27.

### Response `200`

Returns the updated main ticket `TicketResponse`. `duplicateGroupId` is set on the main ticket and
every duplicate. `duplicateGroup` includes `ticketIds` and `canonicalTicketId`. Each affected
ticket also receives a `DUPLICATE_MERGE` `auditHistory` entry.

### Merge error codes

| Code               | Status | Meaning                                                                                                                                                                                                 |
| ------------------ | -----: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `UNAUTHORIZED`     |    401 | Missing, invalid, or expired staff Bearer token.                                                                                                                                                        |
| `TICKET_NOT_FOUND` |    404 | The main ticket or a duplicate ticket ID does not exist.                                                                                                                                                |
| `VALIDATION_ERROR` |    400 | The request violates a merge rule (main ticket listed as duplicate, a duplicate already grouped, categories differ, a ticket is still pending classification, or merging from a non-main group member). |

## `POST /v1/locations/validate`

Validates a citizen-reported location. Accepts either a readable address or a
latitude/longitude pair and returns a normalized location suitable for ticket submission.

### Auth (Sprint 6 target)

Public. This is guest-allowed draft assistance because it creates no ticket or other persistent
contribution. Shared HTTP rate limits apply (`public-location-validate`; see README /
`docs/rate-limiting-runbook.md`).

Uses Amazon Location Service when `LOCATION_PLACE_INDEX_NAME` is configured. When the place
index is unset, the backend falls back to a curated Beirut local place index for local/CI use.

### Request body (address)

```json
{
  "addressText": "AUB Main Gate, Hamra, Beirut"
}
```

### Request body (coordinates)

```json
{
  "latitude": 33.896112,
  "longitude": 35.478419
}
```

### Request fields

| Field         | Type   |    Required | Notes                                                                        |
| ------------- | ------ | ----------: | ---------------------------------------------------------------------------- |
| `addressText` | string | Conditional | Required when coordinates are not provided. Minimum 3 characters after trim. |
| `latitude`    | number | Conditional | Required with `longitude`. Finite value between `-90` and `90`.              |
| `longitude`   | number | Conditional | Required with `latitude`. Finite value between `-180` and `180`.             |

Provide either `addressText` or both coordinates. Partial coordinate pairs are rejected.

### Response `200`

```json
{
  "success": true,
  "location": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "Near AUB Main Gate, Hamra, Beirut",
    "source": "MANUAL"
  },
  "message": "Location validated successfully."
}
```

`source` is `MANUAL` for address lookup and `GPS` for coordinate reverse lookup.

### Location validation error codes

| Code                            | Status | Meaning                                                     |
| ------------------------------- | -----: | ----------------------------------------------------------- |
| `VALIDATION_ERROR`              |    400 | Missing address/coordinates or invalid field values.        |
| `LOCATION_NOT_FOUND`            |    400 | Provider could not resolve the address/point.               |
| `LOCATION_OUT_OF_SERVICE_AREA`  |    400 | Coordinates are outside the supported service area.         |
| `LOCATION_PROVIDER_UNAVAILABLE` |    502 | Amazon Location request failed or returned incomplete data. |

## `POST /v1/uploads/report-photo`

Uploads one citizen report photo to project storage and returns a stable image object key. The
returned `imageObjectKey` should be sent later when creating the report ticket.

This endpoint stores only the image file. It does not create or update a ticket record.
Shared HTTP rate limits apply with a stricter upload budget (`public-upload-report-photo`;
default 10 / 60s) and return `429 RATE_LIMIT_EXCEEDED` with `Retry-After` when exceeded.

### Auth

Requires a contribution-ready citizen Bearer session (same gate as `POST /v1/tickets`, issues
#173 / #194 / #53). Guests receive `401 UNAUTHORIZED`; authenticated citizens whose profile is
not contribution-ready receive `403 CONTRIBUTION_PROFILE_REQUIRED`.

### Request body

Content type: `multipart/form-data`

| Field  | Type       | Required | Notes                                                                                                                                  |
| ------ | ---------- | -------: | -------------------------------------------------------------------------------------------------------------------------------------- |
| `file` | image file |      Yes | Allowed extensions: `jpg`, `jpeg`, `png`, `webp`. Allowed content types: `image/jpeg`, `image/png`, `image/webp`. Maximum size: `5MB`. |

### Response `200`

```json
{
  "imageObjectKey": "reports/photos/2f7b3a5e-4c9d-4a0c-9c1b-8f1234567890.png"
}
```

### Response fields

| Field            | Type   | Notes                                            |
| ---------------- | ------ | ------------------------------------------------ |
| `imageObjectKey` | string | Stable object key for the uploaded report photo. |

### Upload error codes

Upload errors use the common error format.

| Code                | Status | Meaning                                                   |
| ------------------- | -----: | --------------------------------------------------------- |
| `UNAUTHORIZED`                  |    401 | Missing, invalid, or expired citizen session.             |
| `CONTRIBUTION_PROFILE_REQUIRED` |    403 | Session valid but profile is not contribution-ready.      |
| `MISSING_FILE`                  |    400 | No file was provided in the `file` field.                 |
| `INVALID_FILE_TYPE`             |    400 | File extension or content type is not allowed.            |
| `FILE_TOO_LARGE`                |    400 | File is larger than `5MB`.                                |
| `S3_UPLOAD_FAILED`              |    502 | The backend could not upload the file to project storage. |

## Error Format

Validation errors use the following shape.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": [
      {
        "field": "description",
        "message": "String should have at least 10 characters"
      }
    ],
    "requestId": "req_abc123def456"
  }
}
```

### Error fields

| Field                     | Type   | Notes                             |
| ------------------------- | ------ | --------------------------------- |
| `error.code`              | string | Machine-readable error code.      |
| `error.message`           | string | Human-readable summary.           |
| `error.details`           | array  | Field-level validation details.   |
| `error.details[].field`   | string | Field path that caused the error. |
| `error.details[].message` | string | Field-level message.              |
| `error.requestId`         | string | Request identifier for debugging. |

## Common Enums

### `LocationSource`

```text
GPS
MANUAL
PLACEHOLDER
```

### `PreferredChannel`

```text
SMS
EMAIL
```

### `TicketStatus`

Ticket status values use uppercase strings in API responses and storage.

```text
SUBMITTED
UNDER_REVIEW
ASSIGNED
IN_PROGRESS
RESOLVED
CLOSED
```

New submissions always return `SUBMITTED`.

### Allowed status transitions

The backend enforces a strict workflow. Only the transitions below are accepted by
`PATCH /v1/tickets/{ticketId}/status`.

| Current status | Allowed next statuses                 |
| -------------- | ------------------------------------- |
| `SUBMITTED`    | `UNDER_REVIEW`, `CLOSED`              |
| `UNDER_REVIEW` | `ASSIGNED`, `CLOSED`                  |
| `ASSIGNED`     | `IN_PROGRESS`, `UNDER_REVIEW`         |
| `IN_PROGRESS`  | `RESOLVED`, `ASSIGNED`                |
| `RESOLVED`     | `CLOSED`, `IN_PROGRESS`               |
| `CLOSED`       | _(terminal — no further transitions)_ |

Each successful status change appends a row to ticket status history and updates `updatedAt`
and `updatedBy` on the ticket record.

## Shared Ticket Read Shape

Staff dashboard endpoints and ticket read endpoints should return the shared `TicketResponse`
shape below when they need a full ticket summary. This is an API response contract for
frontend/backend alignment. It does not duplicate or replace the persistence model in
[database.md](./database.md).

Backend Pydantic model: `backend/app/schemas/ticket_response.py`

Frontend TypeScript type: `mobile/src/types/ticket.ts`

### `TicketResponse`

```json
{
  "ticketId": "tkt_11111111111111111111111111111111",
  "ticketNumber": "BG-2026-0001",
  "trackingCode": "AB23CD",
  "description": "Large pothole causing traffic near the university entrance.",
  "contact": {
    "name": "Ahmad Khoury",
    "phone": "+96170123456",
    "email": "ahmad.khoury@example.com",
    "preferredChannel": "SMS"
  },
  "ownerUserId": "usr_aaaaaaaaaaaaaaaaaaaaaaaa",
  "category": "road_damage",
  "priority": "high",
  "status": "IN_PROGRESS",
  "location": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "Near AUB Main Gate, Hamra, Beirut",
    "source": "PLACEHOLDER"
  },
  "imageReferences": [
    {
      "objectKey": "reports/mock/pothole-aub-gate.jpg",
      "url": "https://example.test/reports/mock/pothole-aub-gate.jpg",
      "contentType": "image/jpeg",
      "createdAt": "2026-08-12T09:30:00Z"
    }
  ],
  "imageObjectKey": "reports/mock/pothole-aub-gate.jpg",
  "department": {
    "departmentId": "d1111111-1111-1111-1111-111111111111",
    "name": "Roads"
  },
  "departmentId": "d1111111-1111-1111-1111-111111111111",
  "createdBy": "system",
  "municipalityId": "m1111111-1111-1111-1111-111111111111",
  "duplicateGroupId": "99999999-9999-9999-9999-999999999999",
  "createdAt": "2026-08-12T09:30:00Z",
  "updatedAt": "2026-08-12T11:30:00Z",
  "ai": {
    "originalDescription": "Large pothole causing traffic near the university entrance.",
    "cleanedDescription": "Large pothole near the university entrance causing traffic.",
    "aiSuggestedCategory": "road_damage",
    "aiCategoryExplanation": "Road surface defect with traffic impact.",
    "aiProcessingStatus": "completed",
    "aiModelVersion": "amazon.nova-lite-v1:0",
    "finalCategory": "road_damage",
    "categoryReviewedBy": "staff-1",
    "categoryReviewedAt": "2026-08-12T10:00:00Z",
    "suggestedCategory": "road_damage",
    "urgencyScore": 62,
    "urgencyReason": "High (62): possible injury or collision risk; critical location; strong evidence.",
    "summary": "Road damage near AUB Main Gate."
  },
  "statusHistory": [
    {
      "status": "SUBMITTED",
      "changedAt": "2026-08-12T09:30:00Z",
      "changedBy": "system",
      "note": "Ticket submitted."
    }
  ],
  "auditHistory": [
    {
      "actionType": "STATUS_CHANGE",
      "actorId": "staff_admin_001",
      "actorRole": "administrator",
      "summary": "Status changed from SUBMITTED to UNDER_REVIEW.",
      "previousValue": "SUBMITTED",
      "newValue": "UNDER_REVIEW",
      "changedAt": "2026-08-12T09:45:00Z"
    }
  ],
  "duplicateGroup": {
    "duplicateGroupId": "99999999-9999-9999-9999-999999999999",
    "ticketIds": [
      "tkt_22222222222222222222222222222222",
      "tkt_55555555555555555555555555555555"
    ],
    "canonicalTicketId": "tkt_22222222222222222222222222222222"
  },
  "duplicateSuggestions": [
    {
      "ticketId": "tkt_bbbbbbbb444455556666bbbbbbbbbbbb",
      "ticketNumber": "BG-2026-0011",
      "distanceMeters": 73.46,
      "status": "SUBMITTED",
      "category": "road_damage",
      "score": 0.94,
      "categoryMatch": "same"
    }
  ]
}
```

### Required fields

| Field             | Type                    | Notes                                                                                       |
| ----------------- | ----------------------- | ------------------------------------------------------------------------------------------- |
| `ticketId`        | string                  | Internal ticket identifier.                                                                 |
| `trackingCode`    | string                  | Citizen-facing tracking code used by staff and citizen follow-up views.                     |
| `description`     | string                  | Citizen-submitted issue description.                                                        |
| `contact`         | `ReportContact` or null | Citizen contact details when available to staff.                                            |
| `ownerUserId`     | string or null          | Stable citizen owner id when the ticket is account-linked; null for legacy unowned tickets. |
| `category`        | string                  | Current category value, for example `road_damage` or `PENDING_CLASSIFICATION`.              |
| `priority`        | enum or null            | `low`, `medium`, `high`, or `critical`; represents urgency/priority when known.             |
| `status`          | `TicketStatus`          | Current workflow status.                                                                    |
| `location`        | `ReportLocation`        | Same location object used by ticket submission.                                             |
| `imageReferences` | array                   | One or more stable image references for display.                                            |
| `department`      | object or null          | Routed department summary when assigned or suggested.                                       |
| `createdAt`       | string                  | ISO 8601 timestamp.                                                                         |
| `updatedAt`       | string or null          | ISO 8601 timestamp for the latest ticket update.                                            |
| `updatedBy`       | string or null          | Actor identifier for the latest ticket update when available.                               |

### Optional fields

| Field                                   | Type           | Notes                                                                                                                                              |
| --------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ticketNumber`                          | string         | Citizen-facing ticket number when available.                                                                                                       |
| `imageObjectKey`                        | string         | Compatibility field for current staff dashboard clients; mirrors the primary `imageReferences[0].objectKey`.                                       |
| `departmentId`                          | string         | Compatibility field for current staff dashboard clients; mirrors `department.departmentId` when assigned.                                          |
| `department.departmentId`               | string         | Department identifier.                                                                                                                             |
| `department.name`                       | string         | Display name when available.                                                                                                                       |
| `ai.originalDescription`                | string         | Immutable citizen description captured at submission.                                                                                              |
| `ai.cleanedDescription`                 | string         | English-normalized municipal description when available.                                                                                           |
| `ai.aiSuggestedCategory`                | string         | AI category suggestion when available.                                                                                                             |
| `ai.aiCategoryExplanation`              | string         | Short AI explanation for the suggested category.                                                                                                   |
| `ai.aiConfidence`                       | number         | Optional confidence value between `0` and `1` when available.                                                                                      |
| `ai.finalCategory`                      | string         | Staff-approved category when reviewed.                                                                                                             |
| `ai.categoryReviewedBy`                 | string         | Staff actor identifier when the category was reviewed.                                                                                             |
| `ai.categoryReviewedAt`                 | string         | ISO 8601 timestamp for staff category review.                                                                                                      |
| `ai.aiProcessingStatus`                 | enum           | `pending`, `processing`, `completed`, or `failed`.                                                                                                 |
| `ai.aiModelVersion`                     | string         | Bedrock model or processing version identifier when available.                                                                                     |
| `ai.suggestedCategory`                  | string         | Compatibility alias for `ai.aiSuggestedCategory`.                                                                                                  |
| `ai.urgencyScore`                       | number         | Urgency score from `0` to `100` when available.                                                                                                    |
| `ai.urgencyReason`                      | string         | AI explanation for the urgency/priority when available.                                                                                            |
| `ai.summary`                            | string         | AI-generated ticket summary when available.                                                                                                        |
| `statusHistory`                         | array          | Optional workflow history returned by detail APIs.                                                                                                 |
| `statusHistory[].status`                | `TicketStatus` | Status after the change.                                                                                                                           |
| `statusHistory[].changedAt`             | string         | ISO 8601 timestamp for the change.                                                                                                                 |
| `statusHistory[].changedBy`             | string         | Actor identifier when available.                                                                                                                   |
| `statusHistory[].note`                  | string         | Human-readable note when available.                                                                                                                |
| `auditHistory`                          | array          | Staff-only ticket mutation audit trail from issue #143 (empty array when none or when audit storage is temporarily unavailable). Not returned on citizen track responses. |
| `auditHistory[].actionType`             | enum           | `STATUS_CHANGE`, `CATEGORY_REVIEW`, `DEPARTMENT_ASSIGN`, `DUPLICATE_MERGE`, or `PUBLIC_CONTENT_UPDATE`.                                         |
| `auditHistory[].actorId`                | string         | Verified staff actor id from the authenticated principal (client actor fields are not trusted).                                                   |
| `auditHistory[].actorRole`              | enum           | Verified actor role: `municipal_staff` or `administrator` (issue #181).                                                                           |
| `auditHistory[].summary`                | string         | Concise change summary.                                                                                                                            |
| `auditHistory[].previousValue`          | string         | Previous value when applicable.                                                                                                                    |
| `auditHistory[].newValue`               | string         | New value when applicable.                                                                                                                         |
| `auditHistory[].changedAt`              | string         | ISO 8601 timestamp for the change.                                                                                                                 |
| `duplicateGroup`                        | object         | Optional duplicate group reference returned by duplicate-aware APIs.                                                                               |
| `duplicateGroup.duplicateGroupId`       | string         | Duplicate group identifier.                                                                                                                        |
| `duplicateGroup.ticketIds`              | array          | Related ticket IDs when returned.                                                                                                                  |
| `duplicateGroup.canonicalTicketId`      | string         | Primary ticket ID for the group when known.                                                                                                        |
| `duplicateSuggestions`                  | array          | Nearby open, ungrouped duplicate candidates returned by ticket detail APIs; list responses return an empty array.                                  |
| `duplicateSuggestions[].ticketId`       | string         | Internal ID of the suggested ticket.                                                                                                               |
| `duplicateSuggestions[].ticketNumber`   | string         | Citizen-facing number for the suggested ticket when available.                                                                                     |
| `duplicateSuggestions[].distanceMeters` | number         | Approximate distance from the current ticket location.                                                                                             |
| `duplicateSuggestions[].status`         | `TicketStatus` | Current status of the suggested ticket.                                                                                                            |
| `duplicateSuggestions[].category`       | string         | Effective category used for matching, including AI-suggested categories before staff review.                                                       |
| `duplicateSuggestions[].score`          | number         | Optional duplicate confidence score from `0` to `1`.                                                                                               |
| `duplicateSuggestions[].categoryMatch`  | string         | Optional category relationship, either `same` or `similar`.                                                                                        |

### Image reference fields

| Field         | Type   | Required | Notes                                                               |
| ------------- | ------ | -------: | ------------------------------------------------------------------- |
| `objectKey`   | string |      Yes | Stable storage object key.                                          |
| `url`         | string |       No | Temporary or public display URL when the API chooses to return one. |
| `contentType` | string |       No | Image MIME type when known.                                         |
| `createdAt`   | string |       No | ISO 8601 timestamp for the image reference.                         |

## Persistence Mapping

Submitted tickets are persisted using the same JSON field names as this contract. See [database.md](./database.md) for the full DynamoDB model.

### Request → Ticket record

| API request field    | Ticket attribute | Persisted                                             |
| -------------------- | ---------------- | ----------------------------------------------------- |
| `description`        | `description`    | Yes                                                   |
| — (session)          | `ownerUserId`    | Yes (derived from contribution-ready citizen session) |
| — (profile snapshot) | `contact`        | Yes (immutable submission-time snapshot)              |
| `location`           | `location`       | Yes                                                   |
| `imageObjectKey`     | `imageObjectKey` | Yes                                                   |
| `languageHint`       | —                | No                                                    |
| `clientMetadata`     | —                | No                                                    |

### Response → Ticket record

| API response field | Ticket attribute | Persisted          |
| ------------------ | ---------------- | ------------------ |
| `ticketId`         | `ticketId`       | Yes                |
| `ticketNumber`     | `ticketNumber`   | Yes                |
| `trackingCode`     | `trackingCode`   | Yes                |
| `status`           | `status`         | Yes                |
| `createdAt`        | `createdAt`      | Yes                |
| `message`          | —                | No (response-only) |

### Backend defaults (not in API request)

| Ticket attribute   | Default                  | Set by                       |
| ------------------ | ------------------------ | ---------------------------- |
| `category`         | `PENDING_CLASSIFICATION` | Backend on create            |
| `priority`         | `null`                   | AI urgency estimation        |
| `municipalityId`   | `null`                   | Geocoding / routing          |
| `departmentId`     | `null`                   | AI department recommendation |
| `createdBy`        | `null`                   | Authentication               |
| `duplicateGroupId` | `null`                   | Duplicate detection          |
| `updatedAt`        | same as `createdAt`      | Backend on create            |
