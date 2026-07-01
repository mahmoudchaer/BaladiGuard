# BaladiGuard - MVP Tech Stack and API Contract

**Version:** 0.1  
**Date:** 2026-07-01  
**Issue:** #3 - Finalize MVP tech stack and API contract  
**Purpose:** This document defines the recommended MVP stack, architecture, API boundaries, request/response shapes, environment variables, and local development approach so frontend, backend, AWS, and AI work can proceed in parallel.

---

## 1. Project Context

BaladiGuard is a mobile-first civic reporting and municipal maintenance platform. Citizens submit infrastructure complaints with a short description, photo, contact details, and location. The system converts this messy citizen input into a structured municipal ticket that can be reviewed, prioritized, assigned, tracked, and closed by municipality staff.

The MVP focuses on:

1. Citizen report submission.
2. Image upload and storage.
3. Ticket creation with readable ticket number.
4. AI-assisted classification and cleaned descriptions.
5. Location validation and map-ready coordinates.
6. Duplicate detection for nearby similar reports.
7. Explainable urgency scoring.
8. Department suggestion and manual override.
9. Staff dashboard with filters, status updates, map/list view, analytics, and assistant panel.
10. Citizen ticket tracking and notifications.

---

## 2. Recommended MVP Stack

### 2.1 Frontend

**Decision:** Use **React Native + Expo + TypeScript**.

This is the best fit because the project is a mobile app, the team can build Android/iOS from one codebase, and Expo also gives a web option for demos or lightweight dashboard access.

Recommended frontend stack:

| Area | Choice | Notes |
|---|---|---|
| Mobile framework | React Native + Expo | Main app for citizens and staff. |
| Language | TypeScript | Required for safer API contracts. |
| Routing | Expo Router | File-based routes for citizen and staff flows. |
| Forms | React Hook Form + Zod | Frontend validation aligned with backend schemas. |
| API state | TanStack Query | Handles loading, caching, retries, invalidation. |
| Uploads | Expo ImagePicker + S3 presigned URLs | Images go directly to S3 after backend generates upload URL. |
| Location | Expo Location + backend validation | App captures coordinates, backend validates/geocodes with Amazon Location Service. |
| Maps | Amazon Location Service through backend, or MapLibre/react-native-maps for MVP display | Keep provider access hidden from app when possible. |
| Secure storage | Expo SecureStore | Store Cognito tokens or session data securely. |
| UI | React Native Paper or NativeWind | Pick one and stay consistent. For quick MVP, React Native Paper is simple. |
| Testing | Jest + React Native Testing Library | Unit and component tests. |

### 2.2 Backend/API

**Decision:** Use **Python FastAPI** deployed behind **Amazon API Gateway + AWS Lambda**.

Recommended backend stack:

| Area | Choice | Notes |
|---|---|---|
| API framework | FastAPI | Clear OpenAPI docs, Pydantic schemas, easy API contracts. |
| Runtime | Python 3.12 | Stable choice for Lambda and AI/data logic. |
| Lambda adapter | Mangum | Runs FastAPI on AWS Lambda. |
| AWS SDK | boto3 | Interacts with S3, DynamoDB, Bedrock, Location, Rekognition, SNS/SES. |
| Validation | Pydantic v2 | Shared request/response models in backend. |
| Auth verification | Cognito JWT verification | Staff/admin APIs require valid token and role. |
| Testing | pytest + httpx | API contract tests and service tests. |
| Local AWS simulation | LocalStack or DynamoDB Local | Use mocks first, LocalStack when useful. |

For the MVP, a single FastAPI service is enough. Split into separate Lambda functions later only if performance, cost, or deployment complexity requires it.

### 2.3 AWS Services

| Need | AWS service | MVP usage |
|---|---|---|
| API entry point | Amazon API Gateway HTTP API | Public and staff REST API. |
| Backend compute | AWS Lambda | FastAPI backend and processing functions. |
| Ticket data | Amazon DynamoDB | Tickets, users, departments, status history, AI outputs, duplicate groups. |
| Image storage | Amazon S3 | Private bucket for report photos and before/after images. |
| Authentication | Amazon Cognito User Pools | Staff/admin login. Citizen reporting can remain public in MVP. |
| AI text processing | Amazon Bedrock | Classification, cleaned description, summaries, assistant answers. |
| Agent actions | Amazon Bedrock Agent action groups, or backend-orchestrated tools first | Tools: classifyIssue, checkDuplicates, calculateUrgency, assignDepartment, generateReport. |
| Image analysis | Amazon Rekognition | Labels/moderation support for uploaded images. |
| Maps/geocoding | Amazon Location Service | Validate coordinates, reverse geocode, map support. |
| Workflow orchestration | AWS Step Functions | Intake processing pipeline after report creation. Can start as direct backend calls, then move to Step Functions. |
| Notifications | Amazon SNS and/or SES | Ticket creation/update messages. For Lebanon SMS/WhatsApp, add provider integration later if needed. |
| Logs/metrics | Amazon CloudWatch | API logs, Lambda logs, processing failures. |
| Analytics | QuickSight later, API analytics first | MVP can expose analytics cards from DynamoDB queries. |
| Infrastructure | AWS CDK with TypeScript | Repeatable deployment for API, Lambda, DynamoDB, S3, Cognito. |

### 2.4 Repository Structure

Recommended structure:

```text
BaladiGuard/
  apps/
    mobile/
      app/
      src/
        api/
        components/
        features/
          citizen-report/
          ticket-tracking/
          staff-dashboard/
          assistant/
        schemas/
        theme/
      app.json
      package.json
    api/
      app/
        main.py
        core/
          config.py
          security.py
        models/
          ticket.py
          user.py
          department.py
          ai.py
        routers/
          tickets_public.py
          tickets_staff.py
          uploads.py
          analytics.py
          assistant.py
          config.py
        services/
          s3_service.py
          ticket_service.py
          ai_service.py
          location_service.py
          duplicate_service.py
          urgency_service.py
          department_service.py
          notification_service.py
        tests/
      pyproject.toml
  infra/
    cdk/
      lib/
      bin/
      package.json
  docs/
    TECH_STACK_AND_API_CONTRACT.md
    DATABASE_SCHEMA.md
    README_NOTES.md
  scripts/
    seed_sample_data.py
  .github/
    workflows/
      ci.yml
```

---

## 3. High-Level Architecture

```text
Citizen / Staff Mobile App
        |
        | HTTPS JSON API
        v
Amazon API Gateway HTTP API
        |
        v
AWS Lambda running FastAPI
        |
        |-- DynamoDB: tickets, users, departments, events, AI outputs, duplicates
        |-- S3: report images, completion images
        |-- Cognito: staff/admin authentication
        |-- Amazon Location Service: geocoding and coordinate validation
        |-- Rekognition: image labels and unsafe content checks
        |-- Bedrock: classification, cleaning, summaries, assistant answers
        |-- SNS/SES: status update notifications
        |-- CloudWatch: logs and errors
        |
        v
Step Functions intake workflow, optional for first demo but recommended before final demo
```

### 3.1 Intake Processing Flow

1. App asks backend for a presigned S3 upload URL.
2. App uploads image directly to S3.
3. App submits report details and the S3 object key.
4. Backend validates required fields.
5. Backend creates ticket with status `SUBMITTED`.
6. Backend returns `ticketId`, readable `ticketNumber`, and `trackingCode`.
7. Processing workflow starts:
   - Validate/reverse-geocode location.
   - Analyze image labels with Rekognition.
   - Classify issue category with Bedrock or rule-based fallback.
   - Clean the raw description into a municipal description.
   - Check nearby duplicates.
   - Calculate urgency score and explanation.
   - Suggest department.
   - Save AI outputs to ticket.
   - Notify citizen when appropriate.
8. Staff reviews the ticket, accepts or overrides AI suggestions, assigns department/team, updates status, and closes the ticket.

---

## 4. Core Domain Enums

### 4.1 Ticket Status

Use these API keys internally. Display labels can be formatted in the frontend.

```ts
type TicketStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "CLOSED";
```

Default status on creation: `SUBMITTED`.

Recommended normal flow:

```text
SUBMITTED -> UNDER_REVIEW -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED
```

Staff should be allowed to move backward for correction, for example `RESOLVED -> IN_PROGRESS`, when the issue was not actually fixed.

### 4.2 Complaint Categories

MVP categories:

```ts
type CategoryKey =
  | "ROAD_DAMAGE"
  | "STREET_LIGHTING"
  | "WASTE"
  | "WATER_DRAINAGE"
  | "SIDEWALK_ISSUE";
```

Display names:

| Key | Display name | Examples |
|---|---|---|
| ROAD_DAMAGE | Road damage | pothole, cracked asphalt, damaged road edge |
| STREET_LIGHTING | Street lighting | broken streetlight, dark street, exposed lamp wiring |
| WASTE | Waste | garbage pile, overflowing bins, illegal dumping |
| WATER_DRAINAGE | Water / drainage | water leak, blocked drain, flood, sewage smell |
| SIDEWALK_ISSUE | Sidewalk issue | broken sidewalk, blocked pedestrian path, unsafe curb |

### 4.3 Urgency Levels

```ts
type UrgencyLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
```

Recommended score ranges:

| Score | Level |
|---:|---|
| 0-24 | LOW |
| 25-49 | MEDIUM |
| 50-74 | HIGH |
| 75-100 | CRITICAL |

Urgency score should always include an explanation, for example:

```json
{
  "urgencyLevel": "HIGH",
  "urgencyScore": 68,
  "urgencyReason": "Road damage near a university entrance with possible traffic safety risk and 3 nearby duplicate reports."
}
```

### 4.4 Departments

Suggested MVP department keys:

```ts
type DepartmentKey =
  | "PUBLIC_WORKS"
  | "STREET_LIGHTING_UNIT"
  | "SANITATION"
  | "WATER_DRAINAGE_UNIT"
  | "SIDEWALK_MAINTENANCE"
  | "GENERAL_REVIEW";
```

Default mapping:

| Category | Suggested department |
|---|---|
| ROAD_DAMAGE | PUBLIC_WORKS |
| STREET_LIGHTING | STREET_LIGHTING_UNIT |
| WASTE | SANITATION |
| WATER_DRAINAGE | WATER_DRAINAGE_UNIT |
| SIDEWALK_ISSUE | SIDEWALK_MAINTENANCE |

Use `GENERAL_REVIEW` when confidence is low or routing rules are unclear.

---

## 5. Shared Data Shapes

### 5.1 Location Object

```json
{
  "latitude": 33.896112,
  "longitude": 35.478419,
  "addressText": "Near AUB Main Gate, Hamra, Beirut",
  "municipality": "Beirut",
  "district": "Hamra",
  "geohash": "sv8wr...",
  "source": "GPS"
}
```

Rules:

- `latitude` must be between -90 and 90.
- `longitude` must be between -180 and 180.
- `addressText` can be user-entered or reverse-geocoded.
- `geohash` is useful for duplicate detection and map filtering.

### 5.2 Contact Object

```json
{
  "name": "Optional Citizen Name",
  "phone": "+96170123456",
  "email": "citizen@example.com",
  "preferredChannel": "SMS"
}
```

Rules:

- For MVP, contact can be optional, but tracking is more useful if phone or email is provided.
- Never expose contact details to public tracking pages.
- Staff can see contact details only if their role allows it.

### 5.3 Ticket Object

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "ticketNumber": "RD-2026-0042",
  "trackingCode": "9K2M5Q",
  "status": "SUBMITTED",
  "category": "ROAD_DAMAGE",
  "finalCategory": null,
  "urgencyLevel": "HIGH",
  "urgencyScore": 68,
  "urgencyReason": "Road damage near a university entrance with possible safety risk.",
  "departmentKey": "PUBLIC_WORKS",
  "departmentName": "Public Works",
  "originalDescription": "في حفرة كبيرة حد بوابة الجامعة وعم تعمل عجقة",
  "cleanedDescription": "Large pothole reported near the university gate causing traffic disruption.",
  "language": "ARABIZI_OR_ARABIC",
  "image": {
    "objectKey": "reports/2026/07/tkt_01JZABCDEF123456789/photo.jpg",
    "contentType": "image/jpeg",
    "sizeBytes": 842133,
    "previewUrl": null
  },
  "location": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "Near AUB Main Gate, Hamra, Beirut",
    "municipality": "Beirut",
    "district": "Hamra",
    "geohash": "sv8wr...",
    "source": "GPS"
  },
  "ai": {
    "categorySuggestion": "ROAD_DAMAGE",
    "categoryConfidence": 0.91,
    "categoryExplanation": "The report mentions a pothole and traffic disruption.",
    "cleanedDescription": "Large pothole reported near the university gate causing traffic disruption.",
    "imageLabels": ["Road", "Asphalt", "Pothole"],
    "processedAt": "2026-07-01T10:20:30Z",
    "modelId": "bedrock-model-id"
  },
  "duplicates": {
    "duplicateGroupId": null,
    "possibleDuplicates": [
      {
        "ticketId": "tkt_01JZ111111111111111",
        "ticketNumber": "RD-2026-0038",
        "distanceMeters": 42,
        "matchReason": "Same category within 50m"
      }
    ]
  },
  "statusHistory": [
    {
      "status": "SUBMITTED",
      "timestamp": "2026-07-01T10:15:00Z",
      "updatedBy": "system",
      "note": "Ticket created from citizen mobile app."
    }
  ],
  "createdAt": "2026-07-01T10:15:00Z",
  "updatedAt": "2026-07-01T10:20:30Z"
}
```

---

## 6. API Standards

### 6.1 Base URL

```text
Local:      http://localhost:8000/v1
Dev AWS:    https://api-dev.baladiguard.example/v1
Prod AWS:   https://api.baladiguard.example/v1
```

### 6.2 Headers

Public endpoints:

```http
Content-Type: application/json
X-Client-Version: mobile-0.1.0
```

Staff endpoints:

```http
Content-Type: application/json
Authorization: Bearer <cognito_jwt>
X-Client-Version: mobile-0.1.0
```

### 6.3 Success Response Style

Return direct objects for simple endpoints. Use pagination wrapper for list endpoints.

List response:

```json
{
  "items": [],
  "nextPageToken": null,
  "count": 0
}
```

### 6.4 Error Response Style

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": [
      {
        "field": "location.latitude",
        "message": "Latitude must be between -90 and 90."
      }
    ],
    "requestId": "req_01JZABCDEF"
  }
}
```

Common error codes:

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | VALIDATION_ERROR | Missing or invalid request fields. |
| 401 | UNAUTHORIZED | Missing or invalid token. |
| 403 | FORBIDDEN | User does not have permission. |
| 404 | NOT_FOUND | Ticket or resource not found. |
| 409 | CONFLICT | Status transition or merge conflict. |
| 413 | FILE_TOO_LARGE | Uploaded file exceeds limit. |
| 415 | UNSUPPORTED_MEDIA_TYPE | Invalid image type. |
| 429 | RATE_LIMITED | Too many requests. |
| 500 | INTERNAL_ERROR | Unexpected backend error. |

---

## 7. Public Citizen APIs

### 7.1 Create Presigned Upload URL

Used before ticket creation so the app can upload the photo to S3.

```http
POST /v1/uploads/report-photo/presign
```

Request:

```json
{
  "fileName": "pothole.jpg",
  "contentType": "image/jpeg",
  "sizeBytes": 842133
}
```

Response:

```json
{
  "objectKey": "reports/temp/01JZABCDEF/photo.jpg",
  "uploadUrl": "https://s3-presigned-url",
  "method": "PUT",
  "expiresInSeconds": 900,
  "requiredHeaders": {
    "Content-Type": "image/jpeg"
  }
}
```

Validation:

- Allowed types: `image/jpeg`, `image/png`, `image/webp`.
- Suggested MVP max size: 5 MB.
- Generated URLs should expire quickly, for example 15 minutes.

### 7.2 Submit Ticket

```http
POST /v1/tickets
```

Request:

```json
{
  "description": "في حفرة كبيرة حد بوابة الجامعة وعم تعمل عجقة",
  "languageHint": "auto",
  "contact": {
    "name": "Optional Citizen Name",
    "phone": "+96170123456",
    "email": "citizen@example.com",
    "preferredChannel": "SMS"
  },
  "location": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "Near AUB Main Gate, Hamra, Beirut",
    "source": "GPS"
  },
  "imageObjectKey": "reports/temp/01JZABCDEF/photo.jpg",
  "clientMetadata": {
    "platform": "ios",
    "appVersion": "0.1.0"
  }
}
```

Response:

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "ticketNumber": "RD-2026-0042",
  "trackingCode": "9K2M5Q",
  "status": "SUBMITTED",
  "message": "Your report was submitted successfully.",
  "createdAt": "2026-07-01T10:15:00Z"
}
```

Notes:

- The ticket is created immediately with `SUBMITTED` status.
- AI processing can happen asynchronously after the response.
- `ticketNumber` should be citizen-friendly.
- `trackingCode` should be required for public ticket tracking to avoid exposing tickets by ID only.

### 7.3 Track Ticket Publicly

```http
GET /v1/tickets/{ticketNumber}/public?trackingCode=9K2M5Q
```

Response:

```json
{
  "ticketNumber": "RD-2026-0042",
  "status": "IN_PROGRESS",
  "category": "ROAD_DAMAGE",
  "urgencyLevel": "HIGH",
  "publicDescription": "Large pothole reported near the university gate causing traffic disruption.",
  "locationSummary": "Hamra, Beirut",
  "createdAt": "2026-07-01T10:15:00Z",
  "updatedAt": "2026-07-01T14:40:00Z",
  "timeline": [
    {
      "label": "Submitted",
      "timestamp": "2026-07-01T10:15:00Z"
    },
    {
      "label": "Assigned to Public Works",
      "timestamp": "2026-07-01T11:05:00Z"
    },
    {
      "label": "Work in progress",
      "timestamp": "2026-07-01T14:40:00Z"
    }
  ]
}
```

Do not return citizen contact details, staff notes, internal AI confidence, or exact private metadata on the public endpoint.

### 7.4 Citizen Resolution Feedback

Used when a citizen confirms whether the issue was actually fixed.

```http
POST /v1/tickets/{ticketNumber}/public-feedback
```

Request:

```json
{
  "trackingCode": "9K2M5Q",
  "isResolved": true,
  "comment": "The pothole was repaired today."
}
```

Response:

```json
{
  "message": "Thank you for your feedback.",
  "ticketNumber": "RD-2026-0042"
}
```

---

## 8. Staff APIs

All staff APIs require Cognito authentication and staff/admin role.

### 8.1 List Tickets

```http
GET /v1/staff/tickets?status=SUBMITTED&category=ROAD_DAMAGE&urgency=HIGH&departmentKey=PUBLIC_WORKS&limit=20&pageToken=abc
```

Response:

```json
{
  "items": [
    {
      "ticketId": "tkt_01JZABCDEF123456789",
      "ticketNumber": "RD-2026-0042",
      "status": "SUBMITTED",
      "category": "ROAD_DAMAGE",
      "urgencyLevel": "HIGH",
      "departmentKey": "PUBLIC_WORKS",
      "locationSummary": "Hamra, Beirut",
      "createdAt": "2026-07-01T10:15:00Z",
      "updatedAt": "2026-07-01T10:20:30Z"
    }
  ],
  "nextPageToken": null,
  "count": 1
}
```

Supported filters:

- `status`
- `category`
- `urgency`
- `departmentKey`
- `createdAfter`
- `createdBefore`
- `bbox` for map bounds: `west,south,east,north`
- `q` for ticket number or text search, optional later

### 8.2 Get Ticket Details

```http
GET /v1/staff/tickets/{ticketId}
```

Response:

Returns the full ticket object from section 5.3. For S3 images, return a short-lived read URL only when needed:

```json
{
  "ticket": {
    "ticketId": "tkt_01JZABCDEF123456789",
    "ticketNumber": "RD-2026-0042",
    "status": "SUBMITTED"
  },
  "imageReadUrl": "https://s3-presigned-read-url"
}
```

### 8.3 Update Ticket Status

```http
PATCH /v1/staff/tickets/{ticketId}/status
```

Request:

```json
{
  "status": "IN_PROGRESS",
  "note": "Maintenance team started inspection.",
  "notifyCitizen": true
}
```

Response:

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "ticketNumber": "RD-2026-0042",
  "status": "IN_PROGRESS",
  "updatedAt": "2026-07-01T14:40:00Z",
  "statusEvent": {
    "status": "IN_PROGRESS",
    "timestamp": "2026-07-01T14:40:00Z",
    "updatedBy": "usr_staff_123",
    "note": "Maintenance team started inspection."
  }
}
```

### 8.4 Accept or Override AI Category

```http
PATCH /v1/staff/tickets/{ticketId}/category
```

Request:

```json
{
  "finalCategory": "ROAD_DAMAGE",
  "reason": "Accepted AI suggestion."
}
```

Response:

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "aiSuggestedCategory": "ROAD_DAMAGE",
  "finalCategory": "ROAD_DAMAGE",
  "updatedAt": "2026-07-01T11:00:00Z"
}
```

### 8.5 Assign or Override Department

```http
PATCH /v1/staff/tickets/{ticketId}/department
```

Request:

```json
{
  "departmentKey": "PUBLIC_WORKS",
  "reason": "Road repair task."
}
```

Response:

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "departmentKey": "PUBLIC_WORKS",
  "departmentName": "Public Works",
  "updatedAt": "2026-07-01T11:05:00Z"
}
```

### 8.6 Get Duplicate Suggestions

```http
GET /v1/staff/tickets/{ticketId}/duplicates
```

Response:

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "possibleDuplicates": [
    {
      "ticketId": "tkt_01JZ111111111111111",
      "ticketNumber": "RD-2026-0038",
      "category": "ROAD_DAMAGE",
      "status": "SUBMITTED",
      "distanceMeters": 42,
      "matchReason": "Same category within 50m"
    }
  ]
}
```

### 8.7 Merge Duplicate Tickets

```http
POST /v1/staff/duplicates/merge
```

Request:

```json
{
  "primaryTicketId": "tkt_01JZABCDEF123456789",
  "duplicateTicketIds": [
    "tkt_01JZ111111111111111",
    "tkt_01JZ222222222222222"
  ],
  "note": "Same pothole near AUB main gate."
}
```

Response:

```json
{
  "duplicateGroupId": "dup_01JZGROUP123456789",
  "primaryTicketId": "tkt_01JZABCDEF123456789",
  "duplicateTicketIds": [
    "tkt_01JZ111111111111111",
    "tkt_01JZ222222222222222"
  ],
  "updatedAt": "2026-07-01T12:00:00Z"
}
```

Recommended behavior:

- Primary ticket remains active.
- Duplicate tickets should be marked as grouped/duplicate but not deleted.
- Duplicate count should increase urgency score when relevant.

---

## 9. Location APIs

### 9.1 Validate Location

```http
POST /v1/location/validate
```

Request:

```json
{
  "latitude": 33.896112,
  "longitude": 35.478419,
  "addressText": "Near AUB Main Gate, Hamra, Beirut"
}
```

Response:

```json
{
  "valid": true,
  "normalizedLocation": {
    "latitude": 33.896112,
    "longitude": 35.478419,
    "addressText": "AUB Main Gate, Hamra, Beirut, Lebanon",
    "municipality": "Beirut",
    "district": "Hamra",
    "geohash": "sv8wr...",
    "source": "GPS"
  }
}
```

### 9.2 Reverse Geocode Coordinates

```http
POST /v1/location/reverse-geocode
```

Request:

```json
{
  "latitude": 33.896112,
  "longitude": 35.478419
}
```

Response:

```json
{
  "addressText": "Hamra, Beirut, Lebanon",
  "municipality": "Beirut",
  "district": "Hamra"
}
```

---

## 10. AI and Agent APIs

These can be implemented as backend services first. Later, the same functions can become Bedrock Agent action group tools.

### 10.1 Classify Issue

```http
POST /v1/internal/ai/classify-issue
```

Request:

```json
{
  "description": "في حفرة كبيرة حد بوابة الجامعة وعم تعمل عجقة",
  "imageLabels": ["Road", "Asphalt", "Pothole"],
  "locationSummary": "Hamra, Beirut"
}
```

Response:

```json
{
  "category": "ROAD_DAMAGE",
  "confidence": 0.91,
  "explanation": "The text mentions a hole in the road and the image labels suggest road/asphalt damage."
}
```

### 10.2 Clean Description

```http
POST /v1/internal/ai/clean-description
```

Request:

```json
{
  "description": "fi 7ofra ktir kbire 7ad l jem3a w 3am ta3mol 3aj2a",
  "languageHint": "ARABIZI"
}
```

Response:

```json
{
  "cleanedDescription": "Large pothole reported near the university causing traffic disruption.",
  "detectedLanguage": "ARABIZI"
}
```

### 10.3 Process Ticket

```http
POST /v1/internal/tickets/{ticketId}/process
```

Response:

```json
{
  "ticketId": "tkt_01JZABCDEF123456789",
  "processingStatus": "COMPLETED",
  "outputs": {
    "category": "ROAD_DAMAGE",
    "urgencyLevel": "HIGH",
    "departmentKey": "PUBLIC_WORKS",
    "possibleDuplicateCount": 3
  }
}
```

### 10.4 Staff Assistant Query

```http
POST /v1/staff/assistant/query
```

Request:

```json
{
  "message": "Summarize today's urgent unresolved tickets.",
  "filters": {
    "createdAfter": "2026-07-01T00:00:00Z",
    "statusNotIn": ["RESOLVED", "CLOSED"],
    "urgencyIn": ["HIGH", "CRITICAL"]
  }
}
```

Response:

```json
{
  "answer": "There are 4 urgent unresolved tickets today. Two are road damage reports in Hamra, one is a blocked drain, and one is a street lighting issue near a school.",
  "referencedTickets": [
    {
      "ticketId": "tkt_01JZABCDEF123456789",
      "ticketNumber": "RD-2026-0042",
      "summary": "High urgency road damage near AUB main gate."
    }
  ]
}
```

Safety rule:

- The assistant should only answer using ticket data available to the staff role.
- Do not expose private contact details unless the role is allowed.
- For generated summaries, include referenced tickets so staff can verify the answer.

---

## 11. Analytics APIs

### 11.1 Dashboard Overview Cards

```http
GET /v1/staff/analytics/overview
```

Response:

```json
{
  "totalTickets": 120,
  "openTickets": 74,
  "completedTickets": 46,
  "criticalTickets": 5,
  "averageResolutionHours": 38.5
}
```

### 11.2 Category Distribution

```http
GET /v1/staff/analytics/category-distribution
```

Response:

```json
{
  "items": [
    { "category": "ROAD_DAMAGE", "count": 42 },
    { "category": "WASTE", "count": 31 },
    { "category": "STREET_LIGHTING", "count": 20 },
    { "category": "WATER_DRAINAGE", "count": 18 },
    { "category": "SIDEWALK_ISSUE", "count": 9 }
  ]
}
```

### 11.3 Department Summary

```http
GET /v1/staff/analytics/department-summary
```

Response:

```json
{
  "items": [
    {
      "departmentKey": "PUBLIC_WORKS",
      "departmentName": "Public Works",
      "openTickets": 24,
      "resolvedTickets": 17
    }
  ]
}
```

---

## 12. Configuration APIs

These endpoints help the frontend avoid hardcoding labels.

### 12.1 Categories

```http
GET /v1/config/categories
```

Response:

```json
{
  "items": [
    {
      "key": "ROAD_DAMAGE",
      "displayName": "Road damage",
      "description": "Potholes, cracks, unsafe roads, damaged asphalt."
    }
  ]
}
```

### 12.2 Statuses

```http
GET /v1/config/statuses
```

Response:

```json
{
  "items": [
    { "key": "SUBMITTED", "displayName": "Submitted" },
    { "key": "UNDER_REVIEW", "displayName": "Under review" },
    { "key": "ASSIGNED", "displayName": "Assigned" },
    { "key": "IN_PROGRESS", "displayName": "In progress" },
    { "key": "RESOLVED", "displayName": "Resolved" },
    { "key": "CLOSED", "displayName": "Closed" }
  ]
}
```

### 12.3 Departments

```http
GET /v1/config/departments
```

Response:

```json
{
  "items": [
    {
      "key": "PUBLIC_WORKS",
      "displayName": "Public Works",
      "supportedCategories": ["ROAD_DAMAGE", "SIDEWALK_ISSUE"]
    }
  ]
}
```

---

## 13. Environment Variables

### 13.1 Mobile App `.env`

Only expose values that are safe to ship in a mobile app.

```bash
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/v1
EXPO_PUBLIC_AWS_REGION=eu-central-1
EXPO_PUBLIC_COGNITO_USER_POOL_ID=eu-central-1_xxxxx
EXPO_PUBLIC_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
EXPO_PUBLIC_APP_ENV=local
EXPO_PUBLIC_ENABLE_MOCK_API=false
EXPO_PUBLIC_MAP_PROVIDER=amazon_location
```

Do not put AWS secret keys in the mobile app.

### 13.2 Backend `.env`

```bash
APP_ENV=local
AWS_REGION=eu-central-1
LOG_LEVEL=INFO
CORS_ALLOWED_ORIGINS=http://localhost:8081,http://localhost:19006

DYNAMODB_TABLE_NAME=baladiguard-local
S3_REPORT_IMAGES_BUCKET=baladiguard-report-images-local
S3_PRESIGN_EXPIRES_SECONDS=900
MAX_UPLOAD_SIZE_BYTES=5242880
ALLOWED_UPLOAD_CONTENT_TYPES=image/jpeg,image/png,image/webp

COGNITO_USER_POOL_ID=eu-central-1_xxxxx
COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_JWKS_URL=https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_xxxxx/.well-known/jwks.json

BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-or-other-approved-model
BEDROCK_REGION=eu-central-1
ENABLE_BEDROCK=false
AI_FALLBACK_MODE=rules

LOCATION_INDEX_NAME=baladiguard-place-index
LOCATION_MAP_NAME=baladiguard-map
ENABLE_LOCATION_SERVICE=false

REKOGNITION_MIN_CONFIDENCE=70
ENABLE_REKOGNITION=false

DUPLICATE_DISTANCE_METERS=75
URGENCY_HIGH_THRESHOLD=50
URGENCY_CRITICAL_THRESHOLD=75

SNS_TOPIC_ARN=
SES_FROM_EMAIL=no-reply@baladiguard.example
ENABLE_NOTIFICATIONS=false

USE_LOCALSTACK=false
LOCALSTACK_ENDPOINT_URL=http://localhost:4566
DYNAMODB_LOCAL_ENDPOINT=http://localhost:8001
```

### 13.3 Infrastructure `.env`

```bash
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=eu-central-1
PROJECT_NAME=baladiguard
STAGE=dev
DOMAIN_NAME=
ENABLE_QUICKSIGHT=false
```

---

## 14. Local Development Approach

### 14.1 First Working Local Setup

Goal: frontend and backend can work without waiting for real AWS configuration.

Recommended first setup:

1. Create repo structure.
2. Build FastAPI locally with in-memory/mock storage first.
3. Add DynamoDB Local or LocalStack once models stabilize.
4. Use a local folder or mocked S3 service for image references while S3 is being configured.
5. Use rule-based AI fallback until Bedrock credentials and prompts are ready.
6. Use sample tickets for dashboard, map, duplicate, and analytics work.

### 14.2 Backend Commands

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:

```http
GET http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local"
}
```

### 14.3 Mobile Commands

```bash
cd apps/mobile
npm install
npx expo start
```

Use Expo Go for early UI work. Use a development build later if a native map/location dependency requires it.

### 14.4 Mock Mode

Frontend should support mock mode:

```bash
EXPO_PUBLIC_ENABLE_MOCK_API=true
```

When mock mode is enabled:

- Report form returns a fake ticket number.
- Dashboard uses local sample tickets.
- Assistant returns fixed sample answers.
- Map uses sample coordinates.

This lets frontend issues move in parallel with backend and AWS setup.

### 14.5 Seed Data

Sample data should include:

- At least 3 road damage tickets.
- At least 2 nearby duplicates.
- At least 1 ticket in each category.
- At least one critical/high urgency ticket.
- Multiple statuses: `SUBMITTED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`.
- Multilingual descriptions in English, Arabic, French, and Arabizi.

---

## 15. Security and Privacy Rules

1. S3 buckets must be private.
2. Use presigned URLs for upload/download, not public image URLs.
3. Do not store AWS access keys in the mobile app.
4. Staff/admin endpoints require Cognito JWT and role checks.
5. Public tracking must require `ticketNumber` plus `trackingCode`.
6. Public tracking must not expose citizen contact info, internal notes, or staff names.
7. Logs should avoid full contact details and sensitive citizen text where possible.
8. AI prompts should not include unnecessary private fields.
9. Use least-privilege IAM roles for Lambda access to S3, DynamoDB, Bedrock, Rekognition, Location, SNS, and SES.
10. Add rate limiting or throttling on public endpoints before demo if possible.

---

## 16. AI Prompting and Structured Output Rules

All AI functions must return strict JSON matching backend schemas. Do not let the frontend parse free text.

### 16.1 Classification Output Schema

```json
{
  "category": "ROAD_DAMAGE",
  "confidence": 0.91,
  "explanation": "The report mentions a pothole and traffic disruption."
}
```

### 16.2 Cleaning Output Schema

```json
{
  "cleanedDescription": "Large pothole reported near the university causing traffic disruption.",
  "detectedLanguage": "ARABIZI"
}
```

### 16.3 Urgency Output Schema

```json
{
  "urgencyLevel": "HIGH",
  "urgencyScore": 68,
  "urgencyReason": "Road damage near a university entrance with possible safety risk and multiple nearby reports."
}
```

Rules:

- Always preserve original citizen description separately.
- AI suggestions are not final decisions unless staff accepts them or the rule allows auto-acceptance.
- Store confidence and explanation for staff review.
- Low-confidence classifications should be routed to `GENERAL_REVIEW` or highlighted for review.

---

## 17. Sprint/Roadmap Alignment

This document supports parallel work across the existing project issues.

| Work area | Related issues | API/doc impact |
|---|---|---|
| Wireframes and README | #1, #4 | API endpoints and data shapes guide screens and repo docs. |
| Database schema | #2 | Ticket object, status history, AI fields, duplicate groups, departments. |
| Tech stack/API contract | #3 | This file. |
| Citizen report submission | #5, #7, #8, #9, #10, #32, #41 | Upload presign, submit ticket, confirmation response. |
| Staff dashboard basics | #11, #12, #13, #14, #15 | List tickets, get details, update status, filters. |
| AI intake | #16, #17, #18, #19, #20, #21 | Categories, classify, clean, store AI output, staff review. |
| Map/location/duplicates | #22, #23, #24, #25, #26, #27 | Coordinates, location validation, duplicate suggestions, merge endpoint. |
| Urgency and department routing | #28, #29, #30, #31, #33, #34, #35 | Urgency score, explanation, department mapping, filters. |
| Tracking and notifications | #36, #37, #38, #39, #40 | Public tracking, timeline, notification templates. |
| Assistant and analytics | #42, #43, #44, #45, #46, #47 | Staff assistant, summaries, dashboard cards, charts. |
| Demo/testing | #48, #49, #50, #51 | Seed data, multilingual tests, duplicate and urgency tests. |

---

## 18. MVP Implementation Order

Recommended order to avoid blocking teammates:

1. Commit this document and agree on stack decisions.
2. Create repo structure and initial README.
3. Define database schema and backend Pydantic models.
4. Implement health endpoint and config endpoints.
5. Implement upload presign endpoint.
6. Implement submit ticket endpoint with mock/local storage.
7. Add DynamoDB persistence and ticket number generator.
8. Connect frontend report form to backend.
9. Build staff ticket list and details using real API.
10. Add status update workflow and status history.
11. Add AI classification and cleaning with rule fallback first.
12. Add Bedrock integration behind feature flag.
13. Add location validation and coordinates support.
14. Add duplicate detection.
15. Add urgency scoring and department suggestion.
16. Add citizen tracking page and timeline.
17. Add assistant and analytics endpoints.
18. Seed sample data and run end-to-end demo testing.

---

## 19. Open Decisions for Team Agreement

Before implementation starts, the team should confirm these decisions:

1. **One app or two apps:** Recommended MVP is one Expo app with citizen and staff sections. Later, a separate Next.js staff dashboard can be added if needed.
2. **Citizen authentication:** Recommended MVP allows public report submission. Tracking uses ticket number + tracking code. Staff login uses Cognito.
3. **AWS region:** Choose one region where Bedrock, Location, Lambda, DynamoDB, S3, Cognito, and Rekognition are available for the team account.
4. **Notification channel:** SNS/SES for MVP. WhatsApp can be a later integration.
5. **AI auto-approval:** Recommended MVP stores AI suggestions but keeps staff review for final category/department when confidence is low.
6. **Map provider in mobile:** Recommended MVP can display coordinates with a simple map component and keep geocoding through backend/Amazon Location.
7. **Infrastructure tool:** Recommended CDK TypeScript because the app already uses TypeScript and AWS resources need repeatable setup.

---

## 20. Definition of Done for Issue #3

This issue can be considered done when:

- This Markdown file is committed under `docs/TECH_STACK_AND_API_CONTRACT.md`.
- The team confirms React Native + Expo as the frontend stack.
- The team confirms FastAPI + API Gateway + Lambda as the backend/API stack.
- The team confirms DynamoDB and S3 as the MVP data/media layer.
- The team confirms Cognito for staff authentication.
- The team confirms Bedrock, Rekognition, Location Service, and Step Functions as the AWS AI/location/workflow direction.
- Initial endpoints and request/response shapes are available to frontend and backend developers.
- Required environment variables are documented.
- Local development and mock mode are documented.

