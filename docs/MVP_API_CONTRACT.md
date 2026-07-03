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

```text
SUBMITTED
```
