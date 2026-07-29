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
| `Authorization: Bearer <accessToken>` | Staff routes | Required for staff-only ticket endpoints. Issued by `POST /v1/staff/login`. |
| `X-Client-Version` | No | Optional client version, for example `mobile-0.1.0`. |

### Response headers

| Header | Description |
|---|---|
| `X-Request-Id` | Request identifier returned by the backend for tracing errors. |
| `WWW-Authenticate` | Present on `401 UNAUTHORIZED` staff-auth failures (`Bearer`). |

## Staff authentication

Staff credentials are configured on the backend (`STAFF_USERNAME` / `STAFF_PASSWORD`) and signed
with `SECRET_KEY`. This is a temporary shared-credential MVP (not Cognito). Citizen submit and
tracking lookup stay public.

Protected staff routes reject missing/invalid/expired tokens with `401` and code `UNAUTHORIZED`,
without leaking ticket contents or whether a ticket ID exists. Future staff mutations such as
department assignment (issue #141) should reuse the shared `require_staff` dependency.

## `POST /v1/staff/login`

Exchanges staff username/password for a Bearer access token.

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
  "username": "staff",
  "expiresIn": 43200
}
```

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
| `contact` | object | Yes | Citizen contact details. |
| `contact.name` | string | No | Optional citizen name. |
| `contact.phone` | string | Conditional | Required if `contact.email` is not provided. |
| `contact.email` | string | Conditional | Required if `contact.phone` is not provided. |
| `contact.preferredChannel` | enum | No | `SMS` or `EMAIL`. |
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

Returns all persisted tickets using the ticket record shape, sorted by `createdAt` descending.

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
| `contact.preferredChannel` | — | No |
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
