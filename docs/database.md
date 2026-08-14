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
| `ownerHistorySortKey` | string | For account-owned tickets | Derived `createdAt#ticketId` value for stable newest-first citizen history pagination. |
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
| `assignedWorkerId` | string | No | Municipality field worker (`wrk_…`). Mutually exclusive with `assignedTeamId`. |
| `assignedTeamId` | string | No | Municipality field team (`team_…`). Mutually exclusive with `assignedWorkerId`. |
| `suggestedDepartmentId` | string | No | Automatic department suggestion; preserved when staff overrides `departmentId`. |
| `duplicateGroupId` | string | No | Set by duplicate detection. |
| `updatedAt` | string | No | ISO 8601 timestamp of the last update. |

### Staff collection index attributes (issue #267)

Derived on write for indexed staff list/map/aggregates. See [staff-ticket-collection.md](./staff-ticket-collection.md).

| Attribute | Type | Description |
| --- | --- | --- |
| `staffScopeKey` | string | `municipalityId` or `UNSCOPED`. |
| `staffSortKey` | string | `{createdAt}#{ticketId}` for newest-first pagination. |
| `adminBrowseKey` | string | Always `ALL` for administrator browse queries. |

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
| `fullName` | string | No | Optional trimmed 1–120 character name. Not required for contribution (#270). Blank/null clears the name and forces `publicNameVisible=false`. |
| `email` | string, nullable | No | Optional secondary notification/receipt address. Not unique and never used for identity, login, ownership, or automatic recovery. |
| `notificationPreferences` | object | Yes | Opt-in channel/event preferences; defaults to no optional communications. SMS service messages required for authentication are not marketing preferences. |
| `notificationPreferences.ticketUpdates` | enum | Yes | `SMS`, `EMAIL`, `BOTH`, or `NONE`; `EMAIL`/`BOTH` requires non-null email. |
| `notificationPreferences.announcements` | boolean | Yes | Explicit announcement opt-in; default `false`. |
| `publicNameVisible` | boolean | Yes | Default `false`. Public attribution resolves this and current `fullName` dynamically. Empty names cannot be published. |
| `active` | boolean | Yes | Default `true`. OTP verification for an inactive account returns `403 ACCOUNT_INACTIVE` without issuing a session; deactivation immediately revokes existing sessions. |
| `sessionEpoch` | number | Yes | Monotonic account-wide session generation. Phone change and other security revocations increment it; authentication rejects any session whose stored epoch does not match. This is the strongly consistent revocation authority (GSI session scans are best-effort cleanup only). Auth must read the citizen row with DynamoDB `ConsistentRead=True`. Not returned from profile APIs. |
| `createdAt` | string | Yes | ISO 8601 creation time. |
| `updatedAt` | string | Yes | ISO 8601 last profile update time. |

`contributionReady` is derived, not stored: `active = true` and `phoneVerifiedAt` is non-null for the
current phone. `fullName`, `email`, and `publicNameVisible` do not
affect contribution eligibility.

At ticket creation, `notificationPreferences.ticketUpdates` maps into the immutable singular
snapshot as follows: `SMS` → `SMS`, `EMAIL` → `EMAIL`, `BOTH` → `SMS` (MVP primary with email as a
fallback), and `NONE` → null. Profile changes never rewrite this snapshot, but account-linked ticket
notification delivery resolves current profile preferences at send time; legacy unowned tickets keep
using the snapshot.

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

#### Legacy migration (pre-#169 `users` table)

Older local/cloud stacks created `users` with both `phone-index` and `email-index`. Issue #169
removes `email-index` from the authoritative table definition and introduces `phone-claims`,
`citizen-otp-challenges`, and `citizen-sessions`.

Migration behavior:

1. New environments (`make db-migrate` / fresh cloud stack) create the final schema directly.
2. Existing local stacks should `make db-reset` so tables match the definition.
3. Existing cloud stacks must delete or recreate `users` without `email-index` (or explicitly
   delete that GSI), create the three citizen tables, and—if any citizen rows already exist—
   backfill one `phone-claims` item per canonical phone (`phoneKey = PHONE#<E.164>`, `userId`,
   `createdAt`) before serving writes. Empty pre-account environments need no row backfill.
4. Email values on citizen records remain optional non-unique contact data and are never promoted
   to an identity index again.

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
`publicNameVisible` and `fullName`, otherwise returns `Community member`. Profile changes do not rewrite
contact snapshots.

Citizen account deletion (issue #190) anonymizes the `users` row (`active=false`, PII cleared, phone
claim released, tombstone phone `ANON:{userId}`) and revokes sessions. It does **not** rewrite
tickets, contact snapshots, status history, or audit history. See `docs/privacy-lifecycle.md`.

Pre-account tickets remain valid with `ownerUserId = null` and their existing contact shape. They
remain trackable and publicly anonymous. Linking requires verified ownership of the normalized
snapshot phone plus separate ticket proof, uses a conditional `attribute_not_exists(ownerUserId)`
update, and writes an audit event. No migration infers ownership from email or contact data alone.

### StaffUser and authorization scope

Staff identities and credentials are separate from `CitizenUser`. Staff use password-backed MVP
authentication against the `staff-users` table. No staff password hash is stored in a citizen record
or returned by any API. Username uniqueness is enforced by a transactional
`staff-username-claims` record (`usernameKey = USERNAME#<lowercase username>`), not by a GSI alone.

| Attribute | Type | Required | Description |
| --- | --- | --- | --- |
| `staffId` | string | Yes | Stable staff identity key, format `staff_<id>`. |
| `username` | string | Yes | Unique login handle (stored lowercase). |
| `name` | string | Yes | Display name for the admin UI. |
| `email` | string | Yes | Staff contact email (not a citizen identity). |
| `passwordHash` | string | Yes | PBKDF2-HMAC-SHA256 credential metadata. Never returned from APIs or written to logs. |
| `role` | enum | Yes | `municipal_staff` or `administrator`. |
| `municipalityId` | string, nullable | Conditional | Required for `municipal_staff`; null for global administrators. |
| `departmentIds` | string[] or null | Conditional | Assigned departments for `municipal_staff`; `null` for administrators, meaning all departments. An empty array is not a valid administrator sentinel. |
| `active` | boolean | Yes | Inactive staff cannot authenticate; deactivation increments `sessionEpoch`. |
| `sessionEpoch` | number | Yes | Monotonic generation checked on every authenticated request (`ConsistentRead`). Logout and deactivation increment it. |
| `createdAt` | string | Yes | ISO 8601 creation time. |
| `updatedAt` | string | Yes | ISO 8601 last update time. |

Staff authorization is derived from the verified staff session and these stored role/scope fields.
Client-supplied municipality, department, owner, or actor identifiers never expand authority.
Municipal staff may list/read unassigned tickets in their municipality for triage, and may assign
those tickets through the department-assignment action; other ticket mutations require the ticket's
department to be in their assigned scope. Administrators with `departmentIds = null` may operate
across municipalities and departments. Identity/contact reads are least-privilege and audited. The
citizen `users` table and phone-claim table are not used for staff login.

Local/test bootstrap creates demo `admin` (administrator) and `staff` (municipal_staff) accounts
when `SEED_DEMO_STAFF` is enabled; production should keep that flag false and provision real
accounts separately.

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

Staff-only audit trail for **ticket** mutations (issue #143), hardened for verified
actors/roles in Sprint 6 (issue #181). Complements `TicketStatusHistory` without
replacing it. Persisted in both in-memory and DynamoDB-backed modes
(`{prefix}ticket-audit-history`, PK `auditId`, GSI `ticketId-index`).

Audit append and read failures are logged and do **not** roll back a successful primary
mutation or staff ticket response. When audit history cannot be loaded, staff responses return
an empty `auditHistory` array.

`actorId` and `actorRole` come from the authenticated staff principal on HTTP mutations.
Client-provided `updatedBy` / `categoryReviewedBy` / `mergedBy` fields are not trusted.

| Attribute | Type | Description |
| --- | --- | --- |
| `auditId` | string | Primary key. |
| `ticketId` | string | Parent ticket. |
| `actionType` | enum | `STATUS_CHANGE`, `CATEGORY_REVIEW`, `DEPARTMENT_ASSIGN`, or `DUPLICATE_MERGE`. |
| `actorId` | string, nullable | Verified staff actor identifier when available. |
| `actorRole` | enum, nullable | `municipal_staff` or `administrator` from the verified principal (issue #181). |
| `summary` | string | Concise human-readable change summary. |
| `previousValue` | string, nullable | Previous value when applicable. |
| `newValue` | string, nullable | New value when applicable. |
| `createdAt` | string | ISO 8601 timestamp. |

## 5b. AccountAudit

Separate store for **staff/admin account** events (issue #181). Not ticket-scoped and never
mixed into `TicketAuditHistory`. Persisted as `{prefix}account-audit` (PK `auditId`, GSI
`targetStaffId-index`).

Use this boundary for create/role/scope/activation changes, password-reset completion, and
session revoke/logout. Local write failures are logged and never block the primary action.

Payloads must never include passwords, password hashes, access tokens, reset codes, or
unnecessary citizen data. Safe previous/new values are limited to fields such as
`staffId`, `username`, `name`, `role`, `municipalityId`, `departmentIds`, and `active`.

| Attribute | Type | Description |
| --- | --- | --- |
| `auditId` | string | Primary key. |
| `actionType` | enum | See action types below. |
| `actorId` | string, nullable | Verified admin/staff actor when known. |
| `actorRole` | enum, nullable | Actor role when known. |
| `targetStaffId` | string | Account that was created or changed. |
| `summary` | string | Safe human-readable summary. |
| `previousValue` | string, nullable | Safe JSON snapshot or simple value. |
| `newValue` | string, nullable | Safe JSON snapshot or simple value. |
| `createdAt` | string | ISO 8601 timestamp. |

Account audit action types:

```text
STAFF_CREATED
STAFF_ROLE_CHANGED
STAFF_SCOPE_CHANGED
STAFF_DEACTIVATED
STAFF_REACTIVATED
STAFF_PASSWORD_RESET_COMPLETED
STAFF_SESSION_REVOKED
```

Admin account mutations are implemented at
`backend/app/services/staff/admin_accounts.py` with safe append via
`backend/app/services/staff/account_audit.py`.

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

StaffUser (1)
└── AccountAudit (N)
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
| `tickets` | `ticketId` | GSIs on `ticketNumber`, `trackingCode`, `ownerUserId` + `ownerHistorySortKey`, `publicStatus` + `publicSortKey`, `staffScopeKey` + `staffSortKey`, `adminBrowseKey` + `staffSortKey`, `departmentId` + `staffSortKey` (staff collection, issue #267) |
| `users` | `userId` | Optional `phone-index` read optimization only; no email index |
| `phone-claims` | `phoneKey` | Atomic canonical-phone uniqueness authority; no GSI required |
| `citizen-otp-challenges` | `challengeId` | TTL on expiry; optional abuse-control indexes must not expose code material |
| `citizen-sessions` | `sessionId` | GSI on `userId` for account-wide revocation; TTL on expiry |
| `staff-users` | `staffId` | Staff accounts and hashed credentials (#175) |
| `staff-username-claims` | `usernameKey` | Atomic username uniqueness authority |
| `staff-password-reset-challenges` | `challengeId` | Hashed staff reset codes (#178); TTL on `ttl` |
| `municipalities` | `municipalityId` | |
| `departments` | `departmentId` | GSI on `municipalityId` |
| `workforce-workers` | `workerId` | Field workforce directory (#245); GSI on `municipalityId`. Not staff login accounts. |
| `workforce-teams` | `teamId` | Field teams (#245); GSI on `municipalityId`; membership via `workerIds` / worker `teamIds`. |
| `ticket-status-history` | `historyId` | GSI on `ticketId` |
| `ai-outputs` | `aiOutputId` | GSI on `ticketId` |
| `duplicate-groups` | `duplicateGroupId` | |
| `categories` | `categoryId` | Reference taxonomy for AI/admin |
| `counters` | `counterId` | Ticket number sequence counter |
| `rate-limit-buckets` | `bucketKey` | Shared fixed-window rate-limit counters (issue #186); TTL on `expiresAt` |
| `ticket-submission-claims` | `idempotencyKey` | Citizen ticket submit ledger (#258); TTL on `ttl` (~14d completed; shorter for abandoned claims). Covered by backup PITR suffix list. |
