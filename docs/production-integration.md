# Production integration authority (#312)

This document records the real system boundary. `local`, `development`, and
`test` may select explicit deterministic mocks. `staging` and `production`
must fail startup/build rather than silently replace a missing dependency.

## Authoritative user paths

| User-visible capability | Client | Authority / durable path |
| --- | --- | --- |
| Citizen OTP, session, profile, export, deletion | mobile + citizen web | `/v1/citizen/*`; DynamoDB citizen/session/claim tables; SNS for OTP |
| Location validation | mobile + citizen web | `/v1/locations/validate`; Amazon Location in deployed environments |
| Photo upload and claim | mobile + citizen web | `/v1/uploads/report-photo`; private encrypted S3 + DynamoDB upload claims |
| Report submission and history | mobile + citizen web | `/v1/tickets` and `/v1/citizen/me/tickets`; DynamoDB |
| Public browse and safe tracking | mobile + citizen web | public/tracking API projections; only approved redacted image keys |
| Staff authentication and account recovery | admin | `/v1/staff/*`; persisted staff users, sessions, and reset challenges |
| Staff ticket review, routing, comments, assignment | admin | authenticated ticket/workforce APIs; DynamoDB and audit history |
| Work orders, evidence, and resolution feedback | admin | authenticated work-order/feedback APIs; DynamoDB + private S3 |
| AI classification, cleaning, routing, duplicates | backend worker | durable DynamoDB AI queue; Amazon Bedrock |
| Face/plate redaction | redaction worker | durable DynamoDB redaction queue; Rekognition + packaged ONNX model + S3 |
| Citizen status notifications | backend | persisted notification claims/deliveries; SES/SNS real adapter |

## Allowed exceptions

- Mock ticket datasets, mock authentication, local place fixtures, memory
  persistence, and mock notification adapters remain available only when an
  operator explicitly selects a local/development/test mode.
- Unit and integration tests inject fakes directly; missing deployed
  configuration is never interpreted as permission to use them.
- Mobile report drafts and web report drafts are intentionally device/browser
  local until submission. They are not authoritative ticket records.
- The frontend applications contain no AWS credentials. They call the backend;
  only backend runtime identities access DynamoDB, S3, Bedrock, Rekognition,
  Location, SES, and SNS.

## Deployed fail-closed contract

Backend staging and production require DynamoDB, S3, real notification
configuration, a non-placeholder signing secret, Amazon Location, no sample or
demo seeding, HTTPS citizen deep links, and explicit HTTPS CORS origins.

Admin staging/production builds require `VITE_APP_ENV`, a non-localhost HTTPS
API origin, mock mode off, and no browser-bundled staff credentials. Mobile
staging/production builds require a non-localhost HTTPS API URL, mock mode off,
and a real Universal/App Links host. Citizen web applies the equivalent checks.
CI builds every client with a production-shaped configuration and rejects an
unsafe artifact before it can be deployed.

The API and both background workers are separate runtime processes. Deployment
infrastructure (#74) must supervise all three from the same immutable backend
image; the release execution (#54) verifies worker progress and provider access.
