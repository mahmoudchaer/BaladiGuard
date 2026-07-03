# BaladiGuard MVP Tech Stack and API Contract

## 1. Purpose

This document defines the **MVP technology choices** and the **initial API contract** for BaladiGuard so the frontend, backend, and AWS setup can proceed in parallel.

This document is intentionally limited to:

- MVP tech stack choices
- Initial API endpoints
- Request and response shapes
- Required environment variables
- Local development approach

Detailed implementation logic, AI prompt design, business rules, analytics, security policies, roadmap planning, and future workflows should stay in separate tickets or documents.

---

## 2. MVP Tech Stack

| Area | MVP Choice | Notes |
|---|---|---|
| Mobile frontend | React Native + Expo + TypeScript | One mobile codebase for Android and iOS. Expo can also support web previews during development. |
| Frontend routing | Expo Router | Used for app screens such as report submission, ticket tracking, staff ticket list, and ticket details. |
| Frontend API client | Fetch or Axios | Keep one shared API client module for all backend calls. |
| Backend framework | Python + FastAPI | Defines REST endpoints and automatically supports OpenAPI documentation. |
| Backend runtime | AWS Lambda behind Amazon API Gateway | Serverless backend for MVP API endpoints. |
| Database | Amazon DynamoDB | Stores tickets, users, departments, status history, AI outputs, and duplicate groups. |
| File storage | Amazon S3 | Stores uploaded report images. API returns an object key or upload URL. |
| Authentication | Amazon Cognito | Used for staff login. Citizen ticket tracking can remain public through ticket ID lookup for the MVP. |
| AI service | Amazon Bedrock | Used for issue classification, cleaned description, urgency explanation, and staff assistant responses. |
| Image analysis | Amazon Rekognition | Optional MVP service for image labels or moderation if enabled. |
| Location service | Amazon Location Service | Used for geocoding, reverse geocoding, and map support. |
| Notifications | Amazon SNS or SES | Used for ticket creation and status update notifications when enabled. |
| Logging | Amazon CloudWatch | Used for backend logs and error tracking. |
| Mobile deployment | Expo EAS Build | Used to build Android and iOS versions when the app is ready. |
| Backend deployment | API Gateway + Lambda deployment through AWS tooling | Exact deployment method can be finalized by the AWS setup ticket. |

---

## 3. Shared API Conventions

### Base URL

```text
https://api.baladiguard.example.com/v1
```

For local development:

```text
http://localhost:8000/v1
```

### Headers

For public citizen endpoints:

```http
Content-Type: application/json
```

For staff endpoints:

```http
Content-Type: application/json
Authorization: Bearer <cognito_jwt>
```

### Standard Error Response

All endpoints should return a consistent error shape.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "A clear user-facing error message.",
    "details": {}
  }
}
```

### Common Enums

```ts
type TicketStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "CLOSED";

type TicketCategory =
  | "ROAD_DAMAGE"
  | "STREET_LIGHTING"
  | "WASTE"
  | "WATER_DRAINAGE"
  | "SIDEWALK";

type UrgencyLevel =
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "CRITICAL";
```

---

## 4. Initial API Contract

## 4.1 Create Image Upload URL

Used by the mobile app before submitting a report with a photo.

```http
POST /uploads/presign
```

### Request

```json
{
  "fileName": "pothole.jpg",
  "contentType": "image/jpeg"
}
```

### Response

```json
{
  "uploadUrl": "https://s3-presigned-upload-url",
  "objectKey": "reports/2026/07/abc123-pothole.jpg",
  "expiresInSeconds": 900
}
```

---

## 4.2 Submit Citizen Report

Creates a new ticket from citizen input.

```http
POST /reports
```

### Request

```json
{
  "description": "There is a big pothole near the main gate.",
  "language": "en",
  "reporter": {
    "name": "Optional Name",
    "phone": "+96100000000",
    "email": "citizen@example.com"
  },
  "location": {
    "latitude": 33.8966,
    "longitude": 35.4787,
    "address": "Hamra, Beirut"
  },
  "imageObjectKey": "reports/2026/07/abc123-pothole.jpg"
}
```

### Response

```json
{
  "ticketId": "RD-2026-0042",
  "status": "SUBMITTED",
  "message": "Report submitted successfully.",
  "ticket": {
    "id": "ticket_abc123",
    "ticketId": "RD-2026-0042",
    "description": "There is a big pothole near the main gate.",
    "cleanedDescription": "Pothole reported near the main gate.",
    "category": "ROAD_DAMAGE",
    "urgency": "HIGH",
    "department": "PUBLIC_WORKS",
    "createdAt": "2026-07-03T10:15:00Z"
  }
}
```

---

## 4.3 Track Ticket by Ticket ID

Used by citizens to check report progress.

```http
GET /reports/{ticketId}
```

### Response

```json
{
  "ticketId": "RD-2026-0042",
  "status": "IN_PROGRESS",
  "category": "ROAD_DAMAGE",
  "urgency": "HIGH",
  "location": {
    "latitude": 33.8966,
    "longitude": 35.4787,
    "address": "Hamra, Beirut"
  },
  "createdAt": "2026-07-03T10:15:00Z",
  "updatedAt": "2026-07-03T13:30:00Z",
  "timeline": [
    {
      "status": "SUBMITTED",
      "message": "Report submitted.",
      "createdAt": "2026-07-03T10:15:00Z"
    },
    {
      "status": "IN_PROGRESS",
      "message": "Maintenance team assigned.",
      "createdAt": "2026-07-03T13:30:00Z"
    }
  ]
}
```

---

## 4.4 List Staff Tickets

Used by the staff dashboard list and filters.

```http
GET /staff/tickets
```

### Query Parameters

```text
status=SUBMITTED
category=ROAD_DAMAGE
urgency=HIGH
department=PUBLIC_WORKS
limit=20
cursor=optional-pagination-cursor
```

### Response

```json
{
  "items": [
    {
      "id": "ticket_abc123",
      "ticketId": "RD-2026-0042",
      "category": "ROAD_DAMAGE",
      "urgency": "HIGH",
      "status": "IN_PROGRESS",
      "department": "PUBLIC_WORKS",
      "location": {
        "latitude": 33.8966,
        "longitude": 35.4787,
        "address": "Hamra, Beirut"
      },
      "createdAt": "2026-07-03T10:15:00Z",
      "updatedAt": "2026-07-03T13:30:00Z"
    }
  ],
  "nextCursor": null
}
```

---

## 4.5 Get Staff Ticket Details

Used by the staff ticket details page.

```http
GET /staff/tickets/{ticketId}
```

### Response

```json
{
  "id": "ticket_abc123",
  "ticketId": "RD-2026-0042",
  "originalDescription": "There is a big pothole near the main gate.",
  "cleanedDescription": "Pothole reported near the main gate.",
  "category": "ROAD_DAMAGE",
  "aiSuggestedCategory": "ROAD_DAMAGE",
  "aiExplanation": "The description mentions a pothole, which matches road damage.",
  "urgency": "HIGH",
  "urgencyScore": 82,
  "urgencyReason": "High pedestrian and traffic risk near a busy area.",
  "status": "IN_PROGRESS",
  "department": "PUBLIC_WORKS",
  "imageUrl": "https://signed-image-read-url",
  "location": {
    "latitude": 33.8966,
    "longitude": 35.4787,
    "address": "Hamra, Beirut"
  },
  "possibleDuplicates": [
    {
      "ticketId": "RD-2026-0038",
      "distanceMeters": 45,
      "status": "SUBMITTED",
      "category": "ROAD_DAMAGE"
    }
  ],
  "timeline": [
    {
      "status": "SUBMITTED",
      "message": "Report submitted.",
      "createdAt": "2026-07-03T10:15:00Z",
      "createdBy": "citizen"
    }
  ],
  "createdAt": "2026-07-03T10:15:00Z",
  "updatedAt": "2026-07-03T13:30:00Z"
}
```

---

## 4.6 Update Ticket Status

Used by staff to move a ticket through the MVP status workflow.

```http
PATCH /staff/tickets/{ticketId}/status
```

### Request

```json
{
  "status": "IN_PROGRESS",
  "note": "Maintenance team assigned."
}
```

### Response

```json
{
  "ticketId": "RD-2026-0042",
  "status": "IN_PROGRESS",
  "updatedAt": "2026-07-03T13:30:00Z"
}
```

---

## 4.7 Update Ticket Category

Used by staff to accept or correct the AI-suggested category.

```http
PATCH /staff/tickets/{ticketId}/category
```

### Request

```json
{
  "category": "ROAD_DAMAGE",
  "note": "AI suggestion accepted."
}
```

### Response

```json
{
  "ticketId": "RD-2026-0042",
  "category": "ROAD_DAMAGE",
  "updatedAt": "2026-07-03T13:35:00Z"
}
```

---

## 4.8 Update Ticket Department

Used by staff to accept or override the suggested department.

```http
PATCH /staff/tickets/{ticketId}/department
```

### Request

```json
{
  "department": "PUBLIC_WORKS",
  "note": "Assigned to Public Works."
}
```

### Response

```json
{
  "ticketId": "RD-2026-0042",
  "department": "PUBLIC_WORKS",
  "updatedAt": "2026-07-03T13:40:00Z"
}
```

---

## 4.9 Merge Duplicate Tickets

Used by staff when multiple reports describe the same real-world issue.

```http
POST /staff/tickets/{ticketId}/duplicates/merge
```

### Request

```json
{
  "duplicateTicketIds": ["RD-2026-0038", "RD-2026-0039"],
  "note": "Same pothole location."
}
```

### Response

```json
{
  "mainTicketId": "RD-2026-0042",
  "mergedTicketIds": ["RD-2026-0038", "RD-2026-0039"],
  "duplicateGroupId": "dup_group_001"
}
```

---

## 4.10 Staff Assistant Query

Used by the staff dashboard assistant panel.

```http
POST /staff/assistant/query
```

### Request

```json
{
  "message": "Summarize high-priority unresolved tickets today."
}
```

### Response

```json
{
  "answer": "There are 3 high-priority unresolved tickets today. Two are road damage reports in Hamra and one is a drainage issue near a school.",
  "relatedTicketIds": ["RD-2026-0042", "RD-2026-0044", "WD-2026-0011"]
}
```

---

## 5. Required Environment Variables

### Frontend

```text
EXPO_PUBLIC_API_BASE_URL=
EXPO_PUBLIC_AWS_REGION=
EXPO_PUBLIC_COGNITO_USER_POOL_ID=
EXPO_PUBLIC_COGNITO_CLIENT_ID=
EXPO_PUBLIC_LOCATION_MAP_NAME=
```

### Backend

```text
APP_ENV=
AWS_REGION=
CORS_ALLOWED_ORIGINS=

DYNAMODB_TICKETS_TABLE=
DYNAMODB_USERS_TABLE=
DYNAMODB_DEPARTMENTS_TABLE=
DYNAMODB_STATUS_HISTORY_TABLE=
DYNAMODB_DUPLICATE_GROUPS_TABLE=

S3_REPORT_IMAGES_BUCKET=

COGNITO_USER_POOL_ID=
COGNITO_APP_CLIENT_ID=

BEDROCK_MODEL_ID=
BEDROCK_AGENT_ID=
BEDROCK_AGENT_ALIAS_ID=

REKOGNITION_ENABLED=
LOCATION_INDEX_NAME=

SNS_TOPIC_ARN=
SES_FROM_EMAIL=
```

---

## 6. Local Development Approach

### Frontend

The frontend should run locally from the `frontend` folder.

```bash
cd frontend
npm install
npx expo start
```

The frontend should read the API URL from:

```text
EXPO_PUBLIC_API_BASE_URL
```

### Backend

The backend should run locally from the `backend` folder.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### API Documentation

When the FastAPI backend is running locally, the API documentation should be available at:

```text
http://localhost:8000/docs
```

### Local Environment Files

Use local environment files for development values.

```text
frontend/.env.local
backend/.env
```

Do not commit real secrets or AWS credentials.

---

## 7. Agreement Point

Before implementation continues, the team should agree on:

- React Native + Expo + TypeScript for the mobile frontend
- Python + FastAPI for the backend API
- AWS services listed in the MVP tech stack table
- The endpoint names and JSON request/response shapes in this document
