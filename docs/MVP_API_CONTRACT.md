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
| `X-Client-Version` | No | Optional client version, for example `mobile-0.1.0`. |

### Response headers

| Header | Description |
|---|---|
| `X-Request-Id` | Request identifier returned by the backend for tracing errors. |

## Endpoints

## `GET /health`

Returns basic API health status.

### Response `200`

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local"
}
```

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
| `location.latitude` | number | Yes | Latitude between `-90` and `90`. |
| `location.longitude` | number | Yes | Longitude between `-180` and `180`. |
| `location.addressText` | string | Yes | Typed address, landmark, or selected placeholder location text. |
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
  "trackingCode": "AB12CD",
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

## `GET /v1/tickets`

Returns all persisted tickets using the ticket record shape.

### Response `200`

```json
[
  {
    "ticketId": "tkt_2f7b3a5e4c9d4a0c9c1b8f1234567890",
    "ticketNumber": "BG-2026-0001",
    "trackingCode": "AB12CD",
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

Returns one persisted ticket by ID using the ticket record shape.

### Response `200`

```json
{
  "ticketId": "tkt_2f7b3a5e4c9d4a0c9c1b8f1234567890",
  "ticketNumber": "BG-2026-0001",
  "trackingCode": "AB12CD",
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
```

New submissions always return `SUBMITTED`.

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
  "trackingCode": "AB12CD",
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
    "cleanedDescription": "Large pothole near the university entrance causing traffic.",
    "suggestedCategory": "road_damage",
    "urgencyReason": "Traffic disruption and safety risk.",
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
  "duplicateGroup": {
    "duplicateGroupId": "99999999-9999-9999-9999-999999999999",
    "ticketIds": [
      "tkt_22222222222222222222222222222222",
      "tkt_55555555555555555555555555555555"
    ],
    "canonicalTicketId": "tkt_22222222222222222222222222222222"
  }
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
| `priority` | enum or null | `low`, `medium`, or `high`; represents urgency/priority when known. |
| `status` | `TicketStatus` | Current workflow status. |
| `location` | `ReportLocation` | Same location object used by ticket submission. |
| `imageReferences` | array | One or more stable image references for display. |
| `department` | object or null | Routed department summary when assigned or suggested. |
| `createdAt` | string | ISO 8601 timestamp. |
| `updatedAt` | string or null | ISO 8601 timestamp for the latest ticket update. |

### Optional fields

| Field | Type | Notes |
|---|---|---|
| `ticketNumber` | string | Citizen-facing ticket number when available. |
| `imageObjectKey` | string | Compatibility field for current staff dashboard clients; mirrors the primary `imageReferences[0].objectKey`. |
| `departmentId` | string | Compatibility field for current staff dashboard clients; mirrors `department.departmentId` when assigned. |
| `department.departmentId` | string | Department identifier. |
| `department.name` | string | Display name when available. |
| `ai.cleanedDescription` | string | AI-normalized description when available. |
| `ai.suggestedCategory` | string | AI category suggestion when available. |
| `ai.urgencyReason` | string | AI explanation for the urgency/priority when available. |
| `ai.summary` | string | AI-generated ticket summary when available. |
| `statusHistory` | array | Optional workflow history returned by detail APIs. |
| `statusHistory[].status` | `TicketStatus` | Status after the change. |
| `statusHistory[].changedAt` | string | ISO 8601 timestamp for the change. |
| `statusHistory[].changedBy` | string | Actor identifier when available. |
| `statusHistory[].note` | string | Human-readable note when available. |
| `duplicateGroup` | object | Optional duplicate group reference returned by duplicate-aware APIs. |
| `duplicateGroup.duplicateGroupId` | string | Duplicate group identifier. |
| `duplicateGroup.ticketIds` | array | Related ticket IDs when returned. |
| `duplicateGroup.canonicalTicketId` | string | Primary ticket ID for the group when known. |

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
