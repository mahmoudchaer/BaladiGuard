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
| `contact.name` | string | No | Optional citizen name. |
| `contact.phone` | string | Conditional | Required if `contact.email` is absent. |
| `contact.email` | string | Conditional | Required if `contact.phone` is absent. |
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
| `createdBy` | string | No | User identifier once authentication is wired. |
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
| `contact.preferredChannel` | Derived by the client from contact details. |
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

## 4. User

| Attribute | Type | Description |
| --- | --- | --- |
| `userId` | string | Primary key. |
| `municipalityId` | string, nullable | Municipality for staff users. |
| `phone` | string, nullable | Unique when present. |
| `email` | string, nullable | Unique when present. |
| `fullName` | string, nullable | Optional display name. |
| `role` | enum | `citizen` or `municipality_admin`. |
| `reputationScore` | number | Trust score. Default `0`. |
| `createdAt` | string | ISO 8601 timestamp. |

At least one of `phone` or `email` is required for citizen users.

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
├── User (N)
└── Ticket (N)

Department (1)
└── Ticket (N)

User (1)
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
| `users` | `userId` | GSIs on `phone`, `email` |
| `municipalities` | `municipalityId` | |
| `departments` | `departmentId` | GSI on `municipalityId` |
| `ticket-status-history` | `historyId` | GSI on `ticketId` |
| `ai-outputs` | `aiOutputId` | GSI on `ticketId` |
| `duplicate-groups` | `duplicateGroupId` | |
| `categories` | `categoryId` | Reference taxonomy for AI/admin |
| `counters` | `counterId` | Ticket number sequence counter |
