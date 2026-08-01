# BaladiGuard MVP API Contract

This document defines the initial MVP API contract for the mobile app and backend.

## Base API

| Item | Value |
|---|---|
| Base path | `/v1` |
| Request body format | JSON |
| Response body format | JSON |

## Headers

### Request headers

| Header | Required | Description |
|---|---:|---|
| `Content-Type: application/json` | Yes | Required for JSON request bodies. |
| `Authorization: Bearer <accessToken>` | Protected routes | A citizen session token on citizen routes or a staff token on staff routes. Tokens are audience-bound and are not interchangeable. |
| `X-Client-Version` | No | Optional client version, for example `mobile-0.1.0`. |

### Response headers

| Header | Description |
|---|---|
| `X-Request-Id` | Request identifier returned by the backend for tracing errors. |
| `WWW-Authenticate` | Present on `401 UNAUTHORIZED` authentication failures (`Bearer`). |

## Sprint 6 citizen identity and privacy contract

This section is the authoritative target contract for issues #168–#174, #178, #193, and #194.
It is a design contract: routes marked **planned** are not implemented by #193. Until #194 lands,
the current public `POST /v1/tickets` behavior may temporarily differ from the target authorization
rule below.

### Identity and contribution readiness

- A citizen's canonical identity is one verified phone number. `userId` is the stable internal
  ownership key; normalized phone is the unique login and reconciliation key.
- Citizen authentication is passwordless phone OTP. Citizen records and APIs must never accept,
  store, return, or recover a citizen password or password hash.
- Email is nullable secondary contact data for explicitly selected notifications, announcements,
  or receipts. It is not unique, a login identifier, an ownership key, or proof sufficient to
  recover an account after phone loss.
- A citizen is **contribution-ready** only when the session is valid, the account is active,
  `phoneVerifiedAt` is non-null for the account's current phone, and `fullName` is valid after
  trimming (1–120 Unicode characters). OTP verification for an inactive account returns `403
  ACCOUNT_INACTIVE` without a session, while deactivation revokes existing sessions so their next
  use returns `401 UNAUTHORIZED`. An active but incomplete account receives `403
  CONTRIBUTION_PROFILE_REQUIRED` on contribution routes.
- Guests and incomplete citizens may browse public data but may not create tickets or perform any
  other contribution. Clients must never supply `ownerUserId`; protected contribution routes derive
  it from the session.

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

### Planned citizen OTP and session routes

| Route | Guest | Authenticated citizen | Contract |
|---|---:|---:|---|
| `POST /v1/citizen/auth/otp/request` | `LOGIN_OR_SIGNUP` only | Allowed | Accepts phone/region and purpose. `CHANGE_PHONE` requires a valid citizen session and applies only to that session's account; a guest request with that purpose returns `401`. Always returns `202` with a generic response after an authorized, valid request. A code is 6 digits, expires after 5 minutes, is single-use, stores only a keyed hash, and is bound to normalized phone, purpose, challenge ID, and—when changing phone—authenticated `userId`. At most 5 verification attempts are allowed; resend invalidates prior live codes. Per-phone, per-IP, per-account, and per-device throttles apply. |
| `POST /v1/citizen/auth/otp/verify` | `LOGIN_OR_SIGNUP` only | Allowed | Atomically consumes a valid challenge. `LOGIN_OR_SIGNUP` finds or creates the phone identity and returns an opaque citizen Bearer session. An inactive existing account returns `403 ACCOUNT_INACTIVE` after successful phone proof and no session is issued. `CHANGE_PHONE` requires the same authenticated citizen that requested the challenge. Responses before successful phone proof do not reveal whether the phone exists. |
| `POST /v1/citizen/auth/logout` | No | Allowed | Immediately revokes the presented server-side session and returns `204`. Repeating with a revoked token returns `401`. |
| `GET /v1/citizen/me` | No | Allowed | Returns the citizen-safe profile and `contributionReady`; never returns OTP material, internal claims, or credentials. |
| `PATCH /v1/citizen/me` | No | Allowed | Updates supported profile/preferences. A phone change requires a separately verified `CHANGE_PHONE` challenge and an atomic claim transfer. Email changes do not affect identity or sessions. |
| `GET /v1/citizen/tickets` | No | Allowed | Planned account history; derives `userId` from the session and returns only tickets owned by it. |

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

Minimal OTP payloads are fixed as follows:

- OTP request accepts `phone`, optional `region` (required for national-format input), and `purpose`.
  It returns `challengeId`, `expiresIn: 300`, and a generic `message`; it never returns the code.
- OTP verify accepts `challengeId`, `code`, and, for first-time `LOGIN_OR_SIGNUP`, optional
  `fullName`. It returns `accessToken`, `tokenType: "Bearer"`, `expiresIn: 2592000`, and the
  citizen-safe profile.
- `fullName` may be omitted during first verification. The new account then remains authenticated but
  not contribution-ready until a valid name is supplied through `PATCH /v1/citizen/me`.

Successful OTP verification returns one cryptographically random, opaque Bearer access token. Only a
keyed hash is stored in the session record. The MVP session has an absolute 30-day lifetime, does not
slide on use, and has no refresh token. Each login creates a separately revocable session. Logout,
account deactivation, phone change, or an authorized administrative security action revokes affected
sessions immediately; expired and revoked records may be retained briefly for audit and then removed
by TTL. OTP verification does not revoke other sessions unless it changes the phone. Losing access to
a phone is not recoverable through email in the MVP; exceptional recovery requires a separately
approved design.

Malformed phone/challenge input returns `400 VALIDATION_ERROR`. OTP request throttling and exhausted
verification attempts return `429 RATE_LIMITED` (with `Retry-After` where known). An incorrect code
returns `400 INVALID_OTP`; an expired, consumed, or superseded challenge returns `400 OTP_EXPIRED`.
These responses are deliberately account-neutral. A successful verify consumes the challenge in the
same conditional operation that establishes its result so concurrent replay has at most one winner.

Missing, malformed, expired, revoked, logged-out, or wrong-audience credentials return `401
UNAUTHORIZED` with `WWW-Authenticate: Bearer`. A valid session lacking permission or contribution
readiness returns `403` without hiding public resources. Authentication and OTP errors are generic and
must not disclose account existence. Staff login, password storage, authorization, and password
recovery remain a separate staff-only contract; a staff token cannot authenticate a citizen route.

### Public browsing, attribution, and private contact

| Route | Authentication | Public/private rule |
|---|---|---|
| `GET /v1/public/reports` | Public | Planned citizen-safe list/map data only. |
| `GET /v1/public/reports/{ticketNumber}` | Public | Planned citizen-safe report detail only. |
| `GET /v1/tickets/track/{trackingCode}` | Public, possession-based | Existing citizen-safe tracking response; tracking code is not account authentication. |
| `POST /v1/locations/validate` | Public | Guest-allowed draft assistance. It validates input but persists no report or contribution. Existing abuse controls still apply. |
| `POST /v1/uploads/report-photo` | Contribution-ready citizen | Upload creates a persistent contribution artifact and is gated like ticket creation. Guests receive `401`; incomplete citizens receive `403`. |
| `POST /v1/tickets` | Contribution-ready citizen | Planned target behavior. Guests and revoked inactive-account sessions receive `401`; active but incomplete citizens receive `403`. |
| `/v1/staff/**` and staff ticket routes | Authorized staff | Identity/contact is returned only when the staff role and municipality/department scope authorize it. |

Public list, map, and detail responses expose exactly `ticketNumber`, public `status`, approved
`category`, moderated `description`, `location`, optional approved `photoUrl`, `createdAt`,
`updatedAt`, and `submittedBy`. `location` contains a server-generated neighborhood/municipality
`label` plus latitude and longitude rounded to 3 decimal places (about a 110 m latitude grid); it
never contains stored `addressText`, source, or exact coordinates. A report is omitted until its
description/photo are approved for public display; absent/unapproved photos produce no `photoUrl`.
They must not expose `ticketId`, `trackingCode`, `ownerUserId`, phone, email, contact snapshot, device
metadata, internal notes, staff actors, department/municipality IDs, duplicate internals, audit
history, or AI/provider internals. The implementation must use a dedicated public projection and
fail closed rather than serialize a staff model.

`submittedBy` is computed at read time. It is the citizen's current `fullName` only when the ticket
has an `ownerUserId`, that citizen is active, and their current `publicNameVisible` is `true`;
otherwise it is the literal `"Anonymous"`. The default is `false`. Changing the preference or name
therefore affects every existing and future owned report dynamically; turning visibility off hides
all attribution immediately. A name is never copied into the public projection, and legacy/unlinked
tickets are always anonymous.

Ticket ownership and contact have different lifecycles. `ownerUserId` is the immutable stable owner.
`contact` is an immutable submission-time snapshot of the then-current normalized phone, optional
email, full name, and preferred notification channel. Later profile edits do not rewrite it. It is
used for ticket-specific delivery/audit only and is visible solely to authorized staff; public
attribution never reads `contact.name`.

The profile's `notificationPreferences.ticketUpdates` maps to the ticket's singular snapshot
`contact.preferredChannel` as follows: `SMS` → `SMS`, `EMAIL` → `EMAIL`, `BOTH` → `SMS` (MVP primary,
with email available as delivery fallback), and `NONE` → `null`. The snapshot preserves the selected
MVP delivery behavior even if the profile preference later changes.

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

| Role | Identity and scope | Allowed actions |
|---|---|---|
| `citizen` | Stable `userId`; no municipality/department authority. | Public browsing and tracking; own profile/session/history; contribution-ready ticket and photo submission. A citizen can never read another citizen's profile/history or perform staff mutations. |
| `municipal_staff` | Staff identity scoped to one `municipalityId` and one or more assigned `departmentId` values. | Read and mutate tickets in that municipality and assigned departments, according to the route's action; view identity/contact only for authorized operational handling. No staff-account or cross-municipality administration. |
| `administrator` | Staff identity with global municipality/department scope. | All `municipal_staff` actions plus staff/role assignment, municipality and department administration, and cross-scope operational access. |

Route permissions are explicit:

| Route/action | Guest | Citizen | Municipal staff | Administrator |
|---|---:|---:|---:|---:|
| Public map/report list/detail and tracking lookup | Allow | Allow | Allow | Allow |
| `POST /v1/locations/validate` draft validation | Allow | Allow | Allow | Allow |
| OTP request/verify | Login/signup purpose only | Own phone-change purpose | N/A | N/A |
| Current profile, logout, and own history | Deny | Own resources | N/A | N/A |
| `POST /v1/uploads/report-photo` and `POST /v1/tickets` | Deny | Contribution-ready own session | N/A | N/A |
| Staff ticket list/detail and all staff ticket mutations, including status/category/department actions and `POST /v1/tickets/merge` | Deny | Deny | Scoped tickets | All tickets |
| Staff identity/contact fields | Deny | Deny | Authorized operational need and scope only | Authorized administrative need |
| Staff/role, municipality, and department administration | Deny | Deny | Deny | Allow |

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
  "departmentIds": ["d1111111-1111-1111-1111-111111111111", "d3333333-3333-3333-3333-333333333333"],
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

## Endpoints

## `GET /health`

Returns API health status, including optional database connectivity.

The process is considered up when this endpoint responds. Inspect `status` and
`database.status` for dependency health (`ok` or `degraded` / `error`).

### Response `200`

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local",
  "database": {
    "backend": "memory",
    "status": "ok"
  }
}
```

When DynamoDB is configured and unreachable, `status` is `degraded` and
`database.status` is `error`, but the endpoint still returns `200` so basic
liveness checks keep working.

## `POST /v1/tickets`

Creates a submitted citizen report ticket.

### Auth (Sprint 6 target)

Requires a contribution-ready citizen Bearer session. The server derives `ownerUserId` from that
session and snapshots contact data from the citizen profile; client-supplied ownership is forbidden.
Missing authentication and revoked inactive-account sessions return `401`; an active but incomplete
citizen returns `403 CONTRIBUTION_PROFILE_REQUIRED`.
Enforcement is implementation work in #194 and is not implemented by this contract ticket.

### Request body

```json
{
  "description": "Large pothole reported near the university gate causing traffic disruption.",
  "languageHint": "auto",
  "contact": {
    "name": "Citizen Name",
    "phone": "+96170123456",
    "email": "citizen@example.com",
    "preferredChannel": "SMS"
  },
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

| Field | Type | Required | Notes |
|---|---|---:|---|
| `description` | string | Yes | Citizen description of the issue. Minimum 10 characters, maximum 2000 characters. |
| `languageHint` | string | No | Use `auto` by default. |
| `contact` | object | Legacy only | Accepted temporarily before #194 for backward compatibility. After #194, clients must omit it; if supplied, the server returns `400 VALIDATION_ERROR` rather than silently ignoring contact data. The server snapshots the authenticated profile. |
| `contact.name` | string | Legacy only | Replaced by the authenticated citizen's current `fullName` snapshot. |
| `contact.phone` | string | Legacy only | Replaced by the authenticated citizen's canonical verified phone snapshot. |
| `contact.email` | string | Legacy only | Replaced by the authenticated citizen's optional email snapshot. |
| `contact.preferredChannel` | enum | Legacy only | Replaced by the authenticated citizen's notification preference. |
| `location` | object | Yes | Report location. |
| `location.latitude` | number | Yes | Finite latitude between `-90` and `90`, inclusive. |
| `location.longitude` | number | Yes | Finite longitude between `-180` and `180`, inclusive. |
| `location.addressText` | string | Yes | Trimmed readable address, landmark, or selected placeholder location text (3–500 characters). |
| `location.source` | enum | Yes | `GPS`, `MANUAL`, or `PLACEHOLDER`. |
| `imageObjectKey` | string | Yes | Stable image object key/reference used by the backend. |
| `clientMetadata` | object | Yes | Client metadata sent by the mobile app. |
| `clientMetadata.platform` | string | Yes | Example values: `ios`, `android`, `web`. |
| `clientMetadata.appVersion` | string | Yes | Mobile app version. |

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

| Field | Type | Notes |
|---|---|---|
| `ticketId` | string | Internal ticket identifier. |
| `ticketNumber` | string | Citizen-facing ticket number. |
| `trackingCode` | string | Citizen-facing tracking code. |
| `status` | enum | Initial value is `SUBMITTED`. |
| `message` | string | Human-readable confirmation message. |
| `createdAt` | string | ISO 8601 timestamp. |

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

| Field | Type | Notes |
|---|---|---|
| `ticketNumber` | string or null | Citizen-facing ticket number when available. |
| `trackingCode` | string | Citizen-facing tracking code entered by the resident. |
| `status` | `TicketStatus` | Current public workflow status. |
| `category` | string or null | Staff-approved/current public category when available; omitted as null while classification is pending or unapproved. |
| `location.addressText` | string | Public-readable location text only. Coordinates and location source remain staff-only. |
| `createdAt` | string | ISO 8601 timestamp for original submission. |
| `updatedAt` | string or null | ISO 8601 timestamp for the latest ticket update when available. |
| `lastUpdatedAt` | string | `updatedAt` when present, otherwise `createdAt`, for citizen tracking display. |
| `timeline[].status` | `TicketStatus` | Public status reached at this point in the workflow. |
| `timeline[].changedAt` | string | ISO 8601 timestamp for the status change. |

### Staff-only fields excluded from citizen tracking

Citizen tracking responses must not include internal ticket IDs, contact details, photo storage
references, department identifiers, staff actor IDs, municipality IDs, duplicate group data, internal
status notes, authorization data, staff-only controls, or AI/provider implementation details. These
fields remain available only through staff `TicketResponse` endpoints where appropriate.

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

| Code | Status | Meaning |
|---|---:|---|
| `VALIDATION_ERROR` | 400 | The tracking code format is invalid (wrong length or alphabet). |
| `TICKET_NOT_FOUND` | 404 | No ticket exists for a well-formed tracking code. |

## `GET /v1/tickets`

Staff-only. Requires `Authorization: Bearer <accessToken>`.

Returns persisted tickets using the ticket record shape, sorted by `createdAt` descending.
Optional query filters match **persisted** ticket fields and are combined with AND. Omitting a
parameter leaves that dimension unfiltered. An empty match set returns `[]` (HTTP 200), not an
error.

### Query Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `status` | enum | No | Exact match on ticket `status`. One of `SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`. |
| `category` | string | No | Exact match on ticket `category` (including `PENDING_CLASSIFICATION`). Must be a seeded catalog category ID. |
| `urgency` | enum | No | Exact match on persisted urgency level stored as ticket `priority`. One of `low`, `medium`, `high`, `critical`. Tickets with `priority: null` do not match. |
| `departmentId` | string | No | Exact match on assigned `departmentId` (staff override or automatic assignment). Must be a seeded department catalog ID. Does **not** filter on `ai.suggestedDepartmentId`. |

Invalid or blank filter values return `400` with `error.code = VALIDATION_ERROR` and a `details[]`
entry whose `field` is the query parameter name (`status`, `category`, `urgency`, or
`departmentId`).

### Response `200`

```json
[
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
]
```

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

| Field | Type | Required | Notes |
|---|---|---:|---|
| `status` | `TicketStatus` | Yes | Target status. Invalid enum values are rejected with `400` (`VALIDATION_ERROR`). |
| `updatedBy` | string | No | Actor identifier for audit/history (max 120 characters). |
| `note` | string | No | Optional human-readable note (max 500 characters). |

### Response `200`

Returns the updated `TicketResponse`, including `updatedAt`, `updatedBy`, `statusHistory`, and
`auditHistory` (staff audit complements status history).

### Status update error codes

| Code | Status | Meaning |
|---|---:|---|
| `UNAUTHORIZED` | 401 | Missing, invalid, or expired staff Bearer token. |
| `TICKET_NOT_FOUND` | 404 | Ticket ID does not exist. |
| `INVALID_STATUS_TRANSITION` | 400 | Requested status is not allowed from the ticket's current status. |

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

| Field | Type | Required | Notes |
|---|---|---:|---|
| `finalCategory` | string | Yes | One concrete supported category ID. `PENDING_CLASSIFICATION` is not a final category. |
| `categoryReviewedBy` | string | No | Reviewer identifier when authentication provides one (max 120 characters). |

### Response `200`

Returns the updated `TicketResponse`. The top-level `category` and `ai.finalCategory` contain the
approved category. `ai.categoryReviewedAt` is generated by the server, and
`ai.aiSuggestedCategory` remains unchanged. Staff responses also append a `CATEGORY_REVIEW` entry
to `auditHistory`.

### Category review error codes

| Code | Status | Meaning |
|---|---:|---|
| `UNAUTHORIZED` | 401 | Missing, invalid, or expired staff Bearer token. |
| `TICKET_NOT_FOUND` | 404 | Ticket ID does not exist. |
| `VALIDATION_ERROR` | 400 | The category is missing, pending, or not in the supported category catalog. |

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

| Field | Type | Required | Notes |
|---|---|---:|---|
| `departmentId` | string | Yes | Must be one of the seeded department catalog IDs. |
| `updatedBy` | string | No | Staff actor identifier when authentication provides one (max 120 characters). |

### Response `200`

Returns the updated `TicketResponse`. Top-level `department` / `departmentId` reflect the staff
assignment. `ai.suggestedDepartmentId` keeps the original automatic suggestion when present.
Staff responses also append a `DEPARTMENT_ASSIGN` entry to `auditHistory`.

### Department assignment error codes

| Code | Status | Meaning |
|---|---:|---|
| `TICKET_NOT_FOUND` | 404 | Ticket ID does not exist. |
| `VALIDATION_ERROR` | 400 | The department ID is missing or not in the seeded department catalog. |
| `UNAUTHORIZED` | 401 | Missing/invalid staff auth once issue #72 is wired. |

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

| Field | Type | Required | Notes |
|---|---|---:|---|
| `canonicalTicketId` | string | Yes | Main ticket that remains the group representative. |
| `duplicateTicketIds` | string[] | Yes | One or more other ticket IDs to link. Must not include the main ticket. |
| `mergedBy` | string | No | Staff actor identifier when available (max 120 characters). |

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

| Code | Status | Meaning |
|---|---:|---|
| `UNAUTHORIZED` | 401 | Missing, invalid, or expired staff Bearer token. |
| `TICKET_NOT_FOUND` | 404 | The main ticket or a duplicate ticket ID does not exist. |
| `VALIDATION_ERROR` | 400 | The request violates a merge rule (main ticket listed as duplicate, a duplicate already grouped, categories differ, a ticket is still pending classification, or merging from a non-main group member). |

## `POST /v1/locations/validate`

Validates a citizen-reported location. Accepts either a readable address or a
latitude/longitude pair and returns a normalized location suitable for ticket submission.

### Auth (Sprint 6 target)

Public. This is guest-allowed draft assistance because it creates no ticket or other persistent
contribution. Existing rate limits and provider abuse controls apply.

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

| Field | Type | Required | Notes |
|---|---|---:|---|
| `addressText` | string | Conditional | Required when coordinates are not provided. Minimum 3 characters after trim. |
| `latitude` | number | Conditional | Required with `longitude`. Finite value between `-90` and `90`. |
| `longitude` | number | Conditional | Required with `latitude`. Finite value between `-180` and `180`. |

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

| Code | Status | Meaning |
|---|---:|---|
| `VALIDATION_ERROR` | 400 | Missing address/coordinates or invalid field values. |
| `LOCATION_NOT_FOUND` | 400 | Provider could not resolve the address/point. |
| `LOCATION_OUT_OF_SERVICE_AREA` | 400 | Coordinates are outside the supported service area. |
| `LOCATION_PROVIDER_UNAVAILABLE` | 502 | Amazon Location request failed or returned incomplete data. |

## `POST /v1/uploads/report-photo`

Uploads one citizen report photo to project storage and returns a stable image object key. The
returned `imageObjectKey` should be sent later when creating the report ticket.

This endpoint stores only the image file. It does not create or update a ticket record.

### Auth (Sprint 6 target)

Requires a contribution-ready citizen Bearer session because it creates a persistent report artifact.
Missing authentication returns `401`; an incomplete citizen returns `403`. Enforcement is #194 work.

### Request body

Content type: `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---:|---|
| `file` | image file | Yes | Allowed extensions: `jpg`, `jpeg`, `png`, `webp`. Allowed content types: `image/jpeg`, `image/png`, `image/webp`. Maximum size: `5MB`. |

### Response `200`

```json
{
  "imageObjectKey": "reports/photos/2f7b3a5e-4c9d-4a0c-9c1b-8f1234567890.png"
}
```

### Response fields

| Field | Type | Notes |
|---|---|---|
| `imageObjectKey` | string | Stable object key for the uploaded report photo. |

### Upload error codes

Upload errors use the common error format.

| Code | Status | Meaning |
|---|---:|---|
| `MISSING_FILE` | 400 | No file was provided in the `file` field. |
| `INVALID_FILE_TYPE` | 400 | File extension or content type is not allowed. |
| `FILE_TOO_LARGE` | 400 | File is larger than `5MB`. |
| `S3_UPLOAD_FAILED` | 502 | The backend could not upload the file to project storage. |

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

| Field | Type | Notes |
|---|---|---|
| `error.code` | string | Machine-readable error code. |
| `error.message` | string | Human-readable summary. |
| `error.details` | array | Field-level validation details. |
| `error.details[].field` | string | Field path that caused the error. |
| `error.details[].message` | string | Field-level message. |
| `error.requestId` | string | Request identifier for debugging. |

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

| Current status | Allowed next statuses |
|---|---|
| `SUBMITTED` | `UNDER_REVIEW`, `CLOSED` |
| `UNDER_REVIEW` | `ASSIGNED`, `CLOSED` |
| `ASSIGNED` | `IN_PROGRESS`, `UNDER_REVIEW` |
| `IN_PROGRESS` | `RESOLVED`, `ASSIGNED` |
| `RESOLVED` | `CLOSED`, `IN_PROGRESS` |
| `CLOSED` | _(terminal — no further transitions)_ |

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
      "actorId": "staff-1",
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

| Field | Type | Notes |
|---|---|---|
| `ticketId` | string | Internal ticket identifier. |
| `trackingCode` | string | Citizen-facing tracking code used by staff and citizen follow-up views. |
| `description` | string | Citizen-submitted issue description. |
| `contact` | `ReportContact` or null | Citizen contact details when available to staff. |
| `category` | string | Current category value, for example `road_damage` or `PENDING_CLASSIFICATION`. |
| `priority` | enum or null | `low`, `medium`, `high`, or `critical`; represents urgency/priority when known. |
| `status` | `TicketStatus` | Current workflow status. |
| `location` | `ReportLocation` | Same location object used by ticket submission. |
| `imageReferences` | array | One or more stable image references for display. |
| `department` | object or null | Routed department summary when assigned or suggested. |
| `createdAt` | string | ISO 8601 timestamp. |
| `updatedAt` | string or null | ISO 8601 timestamp for the latest ticket update. |
| `updatedBy` | string or null | Actor identifier for the latest ticket update when available. |

### Optional fields

| Field | Type | Notes |
|---|---|---|
| `ticketNumber` | string | Citizen-facing ticket number when available. |
| `imageObjectKey` | string | Compatibility field for current staff dashboard clients; mirrors the primary `imageReferences[0].objectKey`. |
| `departmentId` | string | Compatibility field for current staff dashboard clients; mirrors `department.departmentId` when assigned. |
| `department.departmentId` | string | Department identifier. |
| `department.name` | string | Display name when available. |
| `ai.originalDescription` | string | Immutable citizen description captured at submission. |
| `ai.cleanedDescription` | string | English-normalized municipal description when available. |
| `ai.aiSuggestedCategory` | string | AI category suggestion when available. |
| `ai.aiCategoryExplanation` | string | Short AI explanation for the suggested category. |
| `ai.aiConfidence` | number | Optional confidence value between `0` and `1` when available. |
| `ai.finalCategory` | string | Staff-approved category when reviewed. |
| `ai.categoryReviewedBy` | string | Staff actor identifier when the category was reviewed. |
| `ai.categoryReviewedAt` | string | ISO 8601 timestamp for staff category review. |
| `ai.aiProcessingStatus` | enum | `pending`, `processing`, `completed`, or `failed`. |
| `ai.aiModelVersion` | string | Bedrock model or processing version identifier when available. |
| `ai.suggestedCategory` | string | Compatibility alias for `ai.aiSuggestedCategory`. |
| `ai.urgencyScore` | number | Urgency score from `0` to `100` when available. |
| `ai.urgencyReason` | string | AI explanation for the urgency/priority when available. |
| `ai.summary` | string | AI-generated ticket summary when available. |
| `statusHistory` | array | Optional workflow history returned by detail APIs. |
| `statusHistory[].status` | `TicketStatus` | Status after the change. |
| `statusHistory[].changedAt` | string | ISO 8601 timestamp for the change. |
| `statusHistory[].changedBy` | string | Actor identifier when available. |
| `statusHistory[].note` | string | Human-readable note when available. |
| `auditHistory` | array | Staff-only mutation audit trail (empty array when none or when audit storage is temporarily unavailable). Not returned on citizen track responses. |
| `auditHistory[].actionType` | enum | `STATUS_CHANGE`, `CATEGORY_REVIEW`, `DEPARTMENT_ASSIGN`, or `DUPLICATE_MERGE`. |
| `auditHistory[].actorId` | string | Staff actor identifier when available. |
| `auditHistory[].summary` | string | Concise change summary. |
| `auditHistory[].previousValue` | string | Previous value when applicable. |
| `auditHistory[].newValue` | string | New value when applicable. |
| `auditHistory[].changedAt` | string | ISO 8601 timestamp for the change. |
| `duplicateGroup` | object | Optional duplicate group reference returned by duplicate-aware APIs. |
| `duplicateGroup.duplicateGroupId` | string | Duplicate group identifier. |
| `duplicateGroup.ticketIds` | array | Related ticket IDs when returned. |
| `duplicateGroup.canonicalTicketId` | string | Primary ticket ID for the group when known. |
| `duplicateSuggestions` | array | Nearby open, ungrouped duplicate candidates returned by ticket detail APIs; list responses return an empty array. |
| `duplicateSuggestions[].ticketId` | string | Internal ID of the suggested ticket. |
| `duplicateSuggestions[].ticketNumber` | string | Citizen-facing number for the suggested ticket when available. |
| `duplicateSuggestions[].distanceMeters` | number | Approximate distance from the current ticket location. |
| `duplicateSuggestions[].status` | `TicketStatus` | Current status of the suggested ticket. |
| `duplicateSuggestions[].category` | string | Effective category used for matching, including AI-suggested categories before staff review. |
| `duplicateSuggestions[].score` | number | Optional duplicate confidence score from `0` to `1`. |
| `duplicateSuggestions[].categoryMatch` | string | Optional category relationship, either `same` or `similar`. |

### Image reference fields

| Field | Type | Required | Notes |
|---|---|---:|---|
| `objectKey` | string | Yes | Stable storage object key. |
| `url` | string | No | Temporary or public display URL when the API chooses to return one. |
| `contentType` | string | No | Image MIME type when known. |
| `createdAt` | string | No | ISO 8601 timestamp for the image reference. |

## Persistence Mapping

Submitted tickets are persisted using the same JSON field names as this contract. See [database.md](./database.md) for the full DynamoDB model.

### Request → Ticket record

| API request field | Ticket attribute | Persisted |
|---|---|---|
| `description` | `description` | Yes |
| `contact` | `contact` | Yes |
| `location` | `location` | Yes |
| `imageObjectKey` | `imageObjectKey` | Yes |
| `languageHint` | — | No |
| `contact.preferredChannel` | `contact.preferredChannel` | Yes (nullable snapshot derived from profile preferences) |
| `clientMetadata` | — | No |

### Response → Ticket record

| API response field | Ticket attribute | Persisted |
|---|---|---|
| `ticketId` | `ticketId` | Yes |
| `ticketNumber` | `ticketNumber` | Yes |
| `trackingCode` | `trackingCode` | Yes |
| `status` | `status` | Yes |
| `createdAt` | `createdAt` | Yes |
| `message` | — | No (response-only) |

### Backend defaults (not in API request)

| Ticket attribute | Default | Set by |
|---|---|---|
| `category` | `PENDING_CLASSIFICATION` | Backend on create |
| `priority` | `null` | AI urgency estimation |
| `municipalityId` | `null` | Geocoding / routing |
| `departmentId` | `null` | AI department recommendation |
| `createdBy` | `null` | Authentication |
| `duplicateGroupId` | `null` | Duplicate detection |
| `updatedAt` | same as `createdAt` | Backend on create |
