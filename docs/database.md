# MVP Persistence Model (DynamoDB)

This document defines the MVP persistence model for BaladiGuard. Attribute names match the [MVP API contract](./MVP_API_CONTRACT.md) JSON field names so the mobile app, API, and storage stay aligned.

Citizen submissions are stored as **tickets**. The words "report" and "complaint" are product language only.

> **Note:** An early Postgres/Supabase schema was removed from the repo because it no longer matched this model. MVP persistence is DynamoDB only. The old SQL remains available in git history if needed.

## 1. Ticket

Primary key: `ticketId` (string, format `tkt_<hex>`).

### Submission fields (from `POST /v1/tickets`)

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `description` | string | Yes | Citizen description of the issue. |
| `contact` | object | Yes | Contact snapshot at submission time. |
| `contact.name` | string | Yes for account-owned tickets | Immutable submission-time snapshot of the citizen's full name. Private. |
| `contact.phone` | string | Yes for account-owned tickets | Immutable submission-time snapshot of the citizen's canonical verified E.164 phone. Private. |
| `contact.email` | string, nullable | No | Immutable submission-time snapshot of optional notification email. Private and non-identifying. |
| `contact.preferredChannel` | enum, nullable | No | Immutable submission-time notification choice: `SMS`, `EMAIL`, or null when ticket updates are disabled. |
| `location` | object | Yes | Report location. |
| `location.latitude` | number | Yes | Finite latitude between `-90` and `90`, inclusive. |
| `location.longitude` | number | Yes | Finite longitude between `-180` and `180`, inclusive. |
| `location.addressText` | string | Yes | Trimmed readable address, landmark, or placeholder text (3–500 characters). |
| `location.source` | enum | Yes | `GPS`, `MANUAL`, or `PLACEHOLDER`. |
| `imageObjectKey` | string | Yes | S3 object key for the uploaded photo. |

### Backend-generated fields (from `POST /v1/tickets` response)

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `ticketId` | string | Yes | Primary key. Format: `tkt_<hex>`. |
| `ownerUserId` | string, nullable | No | Stable citizen owner derived from authentication. Null/absent only for legacy/unlinked tickets. Never accepted from a client. |
| `ticketNumber` | string | Yes | Citizen-facing ticket number, e.g. `BG-2026-0001`. |
| `trackingCode` | string | Yes | Citizen-facing tracking code, e.g. `AB12CD`. |
| `status` | enum | Yes | Initial value: `SUBMITTED`. |
| `createdAt` | string | Yes | ISO 8601 timestamp. |

### Workflow / AI fields (populated after submission)

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `category` | string | Yes | Defaults to `PENDING_CLASSIFICATION` until AI classification runs. Mirrors `finalCategory` after staff review. |
| `originalDescription` | string | Yes | Immutable citizen text captured at submission. Mirrors `description`. |
| `cleanedDescription` | string, nullable | No | AI-cleaned municipal description from issue #18. |
| `aiSuggestedCategory` | string, nullable | No | AI category suggestion from issue #17. Never overwritten by staff review. |
| `aiCategoryExplanation` | string, nullable | No | Short AI explanation for the suggested category. |
| `aiConfidence` | number, nullable | No | `0` to `1` when the implementation provides a meaningful confidence value. |
| `finalCategory` | string, nullable | No | Staff-approved category, separate from `aiSuggestedCategory`. |
| `categoryReviewedBy` | string, nullable | No | Staff actor identifier when the category is reviewed. |
| `categoryReviewedAt` | string, nullable | No | ISO 8601 timestamp when staff reviewed the category. |
| `aiProcessingStatus` | enum | Yes | `pending`, `processing`, `completed`, or `failed`. Defaults to `pending` at submission. Conditionally moves to `processing` when a worker claims the AI job. Startup recovery only reclaims `processing` tickets whose `updatedAt` is older than `AI_PROCESSING_CLAIM_TIMEOUT_SECONDS` (default 300). |
| `aiModelVersion` | string, nullable | No | Bedrock model or processing version identifier when available. |
| `priority` | enum | No | `low`, `medium`, `high`, or `critical`. Set by AI urgency estimation. |
| `urgencyScore` | number, nullable | No | Urgency score from `0` to `100` when available. |
| `urgencyReason` | string, nullable | No | Staff-facing explanation for the urgency score when available. |
| `createdBy` | string | No | Staff/system actor identifier for workflow mutations; citizen ownership uses `ownerUserId`. |
| `municipalityId` | string | No | Set by geocoding / municipality routing. |
| `departmentId` | string | No | Staff-assigned / currently effective department. |
| `suggestedDepartmentId` | string | No | Automatic department suggestion; preserved when staff overrides `departmentId`. |
| `duplicateGroupId` | string | No | Set by duplicate detection. |
| `updatedAt` | string | No | ISO 8601 timestamp of the last update. |

### Not persisted

These API request fields are accepted at submission time but are not stored on the ticket record in MVP:

| API field | Reason |
| --- | --- |
| `languageHint` | Client default; processed transiently when AI is wired. |
| `clientMetadata` | Ephemeral client telemetry for the request lifecycle. |

## 2. Municipality

| Attribute | Type | Description |
| --- | --- | --- |
| `municipalityId` | string | Primary key. |
| `name` | string | Municipality name. |
| `city` | string | City. |
| `governorate` | string | Governorate. |
| `createdAt` | string | ISO 8601 timestamp. |

## 3. Department

| Attribute | Type | Description |
| --- | --- | --- |
| `departmentId` | string | Primary key. |
| `municipalityId` | string | Parent municipality. |
| `name` | string | Department name. |
| `description` | string | Department responsibilities. |

## 4. CitizenUser

Citizen identities are separate from staff credential records. A citizen has no password hash,
password metadata, reset token, or email identity. Staff may continue to use a separate password
contract and persistence model.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `userId` | string | Yes | Stable primary/ownership key, format `usr_<hex>`. Never changes with profile fields. |
| `phone` | string | Yes | Canonical verified E.164 phone and login/reconciliation key. |
| `phoneVerifiedAt` | string | Yes | ISO 8601 time at which the current `phone` was verified. Replaced atomically on phone change. |
| `fullName` | string | Yes for contribution | Trimmed 1–120 character name. May be temporarily absent only during first verified-phone onboarding. |
| `email` | string, nullable | No | Optional secondary notification/receipt address. Not unique and never used for identity, login, ownership, or automatic recovery. |
| `notificationPreferences` | object | Yes | Opt-in channel/event preferences; defaults to no optional communications. SMS service messages required for authentication are not marketing preferences. |
| `notificationPreferences.ticketUpdates` | enum | Yes | `SMS`, `EMAIL`, `BOTH`, or `NONE`; `EMAIL`/`BOTH` requires non-null email. |
| `notificationPreferences.announcements` | boolean | Yes | Explicit announcement opt-in; default `false`. |
| `publicNameVisible` | boolean | Yes | Default `false`. Public attribution resolves this and current `fullName` dynamically. |
| `active` | boolean | Yes | Default `true`. OTP verification for an inactive account returns `403 ACCOUNT_INACTIVE` without issuing a session; deactivation immediately revokes existing sessions. |
| `createdAt` | string | Yes | ISO 8601 creation time. |
| `updatedAt` | string | Yes | ISO 8601 last profile update time. |

`contributionReady` is derived, not stored: `active = true`, `phoneVerifiedAt` is non-null for the
current phone, and trimmed `fullName` is 1–120 characters. `email` and `publicNameVisible` do not
affect contribution eligibility.

At ticket creation, `notificationPreferences.ticketUpdates` maps into the immutable singular
snapshot as follows: `SMS` → `SMS`, `EMAIL` → `EMAIL`, `BOTH` → `SMS` (MVP primary with email as a
fallback), and `NONE` → null. Profile changes never rewrite this snapshot.

### Phone normalization and atomic uniqueness

The sole canonical representation is E.164 (`+` plus 8–15 digits). Every account, OTP, login,
lookup, phone change, legacy linking, and future WhatsApp path must use the exact normalization rules
in [the API contract](./MVP_API_CONTRACT.md#canonical-phone-normalization) before persistence.

A `phone-claims` table provides the uniqueness authority:

| Attribute | Type | Description |
| --- | --- | --- |
| `phoneKey` | string | Partition key, exact value `PHONE#<canonical E.164>`. |
| `userId` | string | Owner of the claimed phone. |
| `createdAt` | string | ISO 8601 claim time. |

Account creation uses one DynamoDB `TransactWriteItems`: conditionally put the claim with
`attribute_not_exists(phoneKey)` and put the citizen record with `attribute_not_exists(userId)`.
Either both succeed or neither does. A phone change first verifies a purpose-bound OTP, then one
transaction conditionally creates the new claim, conditionally updates the user while the old phone
still matches, and deletes the old claim only when its `userId` matches. Deactivation retains the
claim so another person cannot silently inherit the identity; release/reassignment is outside MVP.
A `phone-index` GSI on users may be retained only as a read optimization/reconciliation aid and is
never used to enforce uniqueness. There is no `email-index`.

### Citizen sessions and OTP challenges

`citizen-otp-challenges` stores challenge ID, keyed code hash, canonical phone, purpose, expiry,
attempt count, consumed time, and abuse-control metadata with TTL cleanup. Plain OTP codes are never
stored. Conditional updates enforce single use and the five-attempt limit.

`citizen-sessions` stores a session ID/partition key, keyed token hash, `userId`, creation/expiry,
revocation time/reason, and last-seen metadata. Opaque tokens expire absolutely after 30 days.
Logout and security events revoke server-side records immediately. These records contain no citizen
password fields or staff credentials.

### Ticket ownership, privacy, and legacy data

`ownerUserId` is immutable ownership; `contact` is the immutable private submission snapshot. Public
name attribution never reads the snapshot: it dynamically resolves the active owner's current
`publicNameVisible` and `fullName`, otherwise returns `Anonymous`. Profile changes do not rewrite
contact snapshots.

Pre-account tickets remain valid with `ownerUserId = null` and their existing contact shape. They
remain trackable and publicly anonymous. Linking requires verified ownership of the normalized
snapshot phone plus separate ticket proof, uses a conditional `attribute_not_exists(ownerUserId)`
update, and writes an audit event. No migration infers ownership from email or contact data alone.

### StaffUser and authorization scope

Staff identities and credentials are separate from `CitizenUser`. Staff may retain the existing
password-backed MVP authentication; no staff password hash is stored in a citizen record or returned
by any API. The staff principal used for authorization contains:

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `staffId` | string | Yes | Stable staff identity key. |
| `role` | enum | Yes | `municipal_staff` or `administrator`. |
| `municipalityId` | string, nullable | Conditional | Required for `municipal_staff`; null for global administrators. |
| `departmentIds` | string[] | Yes | Assigned departments for `municipal_staff`; all departments for administrators. |
| `active` | boolean | Yes | Inactive staff cannot authenticate; deactivation revokes staff sessions. |
| `createdAt` | string | Yes | ISO 8601 creation time. |
| `updatedAt` | string | Yes | ISO 8601 last update time. |

Staff authorization is derived from the verified staff session and these stored role/scope fields.
Client-supplied municipality, department, owner, or actor identifiers never expand authority.
Municipal staff may operate only on tickets in their municipality and assigned departments;
administrators may operate across municipalities. Identity/contact reads are least-privilege and
audited. A separate staff persistence/credential table may be introduced by the staff-auth work;
the citizen `users` table and phone-claim table are not used for staff login.

## 5. TicketStatusHistory

| Attribute | Type | Description |
| --- | --- | --- |
| `historyId` | string | Primary key. |
| `ticketId` | string | Parent ticket. |
| `previousStatus` | enum, nullable | Previous ticket status. |
| `newStatus` | enum | New ticket status. |
| `updatedBy` | string | User who made the change. |
| `note` | string, nullable | Optional note. |
| `createdAt` | string | ISO 8601 timestamp. |

## 5a. TicketAuditHistory

Staff-only audit trail for ticket mutations (issue #143). Complements `TicketStatusHistory`
without replacing it. Persisted in both in-memory and DynamoDB-backed modes
(`{prefix}ticket-audit-history`, PK `auditId`, GSI `ticketId-index`).

Audit append and read failures are logged and do **not** roll back a successful primary
mutation or staff ticket response. When audit history cannot be loaded, staff responses return
an empty `auditHistory` array.

| Attribute | Type | Description |
| --- | --- | --- |
| `auditId` | string | Primary key. |
| `ticketId` | string | Parent ticket. |
| `actionType` | enum | `STATUS_CHANGE`, `CATEGORY_REVIEW`, `DEPARTMENT_ASSIGN`, or `DUPLICATE_MERGE`. |
| `actorId` | string, nullable | Staff actor identifier when available. |
| `summary` | string | Concise human-readable change summary. |
| `previousValue` | string, nullable | Previous value when applicable. |
| `newValue` | string, nullable | New value when applicable. |
| `createdAt` | string | ISO 8601 timestamp. |

## 6. AiOutput

| Attribute | Type | Description |
| --- | --- | --- |
| `aiOutputId` | string | Primary key. |
| `ticketId` | string | Parent ticket (one per ticket). |
| `cleanedDescription` | string, nullable | AI-cleaned description. |
| `predictedCategory` | string, nullable | AI category prediction. |
| `confidence` | number, nullable | `0` to `1`. |
| `urgencyScore` | number, nullable | `0` to `100`. |
| `urgencyReason` | string, nullable | Explanation. |
| `suggestedDepartmentId` | string, nullable | Recommended department. |
| `summary` | string, nullable | AI-generated summary. |
| `createdAt` | string | ISO 8601 timestamp. |

## 7. DuplicateGroup

| Attribute | Type | Description |
| --- | --- | --- |
| `duplicateGroupId` | string | Primary key. |
| `canonicalTicketId` | string | Main ticket staff chose for the group. |
| `ticketIds` | string[] | All linked report IDs (main + duplicates). |
| `createdAt` | string | ISO 8601 timestamp. |
| `createdBy` | string, nullable | Staff actor when merge is recorded. |

Staff merge (`POST /v1/tickets/merge`, issue #27) creates a DuplicateGroup row and stamps
`duplicateGroupId` onto every member ticket. Ticket read responses may also include an enriched
`duplicateGroup` object with the linked IDs. Merging again from the main ticket appends new
duplicates to the same group; already-grouped duplicates and cross-category merges are
rejected, and unmerge is out of scope for issue #27.

### Nearby duplicate detection (issue #25)

Detection is a standalone backend helper (`find_nearby_duplicates`) and does **not** yet
persist `duplicateGroupId` or create DuplicateGroup rows (staff merge is issue #27).

Inputs: query category, latitude/longitude, and a required sequence of tickets to search
(plus an optional `exclude_ticket_id` so a ticket is not matched against itself).

Behavior:
- Considers only open tickets: `SUBMITTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`
- Matches the same category, or a similar category that shares a department mapping
  (today: `road_damage` ↔ `sidewalk_damage`)
- Uses haversine distance in meters
- Configurable via `DUPLICATE_DISTANCE_THRESHOLD_M` (default `100`), `DUPLICATE_MIN_SCORE`
  (default `0.4`), and category weight env vars
- Returns candidate `ticketId`, `distanceMeters`, `score`, `category`, `categoryMatch`, and `status`

## Relationships

```text
Municipality (1)
├── Department (N)
└── Ticket (N)

Department (1)
└── Ticket (N)

CitizenUser (1)
└── Ticket (N)

Ticket (1)
├── TicketStatusHistory (N)
├── TicketAuditHistory (N)
├── AiOutput (1)
└── DuplicateGroup (N:1)
```

## Enums

### Ticket status (API and storage)

```text
SUBMITTED
UNDER_REVIEW
ASSIGNED
IN_PROGRESS
RESOLVED
CLOSED
```

Allowed transitions (strict workflow):

| From | To |
|---|---|
| `SUBMITTED` | `UNDER_REVIEW`, `CLOSED` |
| `UNDER_REVIEW` | `ASSIGNED`, `CLOSED` |
| `ASSIGNED` | `IN_PROGRESS`, `UNDER_REVIEW` |
| `IN_PROGRESS` | `RESOLVED`, `ASSIGNED` |
| `RESOLVED` | `CLOSED`, `IN_PROGRESS` |
| `CLOSED` | _(none)_ |

### Report priority (AI / admin domain)

```text
low
medium
high
critical
```

Urgency levels map to scores in `docs/urgency-scoring.md`; `critical` covers scores 75-100.

### Location source

```text
GPS
MANUAL
PLACEHOLDER
```

## Default values at submission

When a ticket is created from `POST /v1/tickets`, the backend sets:

| Attribute | Default |
| --- | --- |
| `status` | `SUBMITTED` |
| `category` | `PENDING_CLASSIFICATION` |
| `createdAt` | current UTC timestamp |
| `updatedAt` | same as `createdAt` |
| `updatedBy` | `null` |
| `originalDescription` | same as `description` |
| `aiProcessingStatus` | `pending` |

An initial status-history entry is also created with `newStatus = SUBMITTED`.

## DynamoDB tables (local and cloud)

See [local-database-setup.md](./local-database-setup.md) for Docker local commands and
[cloud-setup.md](./cloud-setup.md) for AWS cloud configuration.

| Table suffix | Partition key | Notes |
|---|---|---|
| `tickets` | `ticketId` | GSIs on `ticketNumber`, `trackingCode` |
| `users` | `userId` | Optional `phone-index` read optimization only; no email index |
| `phone-claims` | `phoneKey` | Atomic canonical-phone uniqueness authority; no GSI required |
| `citizen-otp-challenges` | `challengeId` | TTL on expiry; optional abuse-control indexes must not expose code material |
| `citizen-sessions` | `sessionId` | GSI on `userId` for account-wide revocation; TTL on expiry |
| `municipalities` | `municipalityId` | |
| `departments` | `departmentId` | GSI on `municipalityId` |
| `ticket-status-history` | `historyId` | GSI on `ticketId` |
| `ai-outputs` | `aiOutputId` | GSI on `ticketId` |
| `duplicate-groups` | `duplicateGroupId` | |
| `categories` | `categoryId` | Reference taxonomy for AI/admin |
| `counters` | `counterId` | Ticket number sequence counter |
