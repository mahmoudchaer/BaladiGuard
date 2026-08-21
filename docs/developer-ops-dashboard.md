# Developer operations dashboard (issue #320)

Private control plane for BaladiGuard **developer operators**. Municipality
staff, municipality administrators, and citizens cannot use it.

## Who can sign in

- Role: `developer_operator`
- Local/test demo account (when `SEED_DEMO_STAFF=true`): username `operator`,
  password `DEMO_STAFF_PASSWORD` (default `staff-demo-password`)
- Production first account: set `DEVELOPER_OPERATOR_USERNAME` and
  `DEVELOPER_OPERATOR_PASSWORD` (min 8 chars). The API creates the account on
  startup if that username does not already exist.
- Municipality administrators **cannot** create or promote this role via
  `/v1/admin/staff-accounts`.

## How to open it

1. Start the API and admin app as usual.
2. Sign in at the staff login page as `operator`.
3. You are sent to `/ops`. Ticket/map/workforce routes stay hidden and return
   403 from the API.

## What the UI shows

| Tab | Source | Notes |
| --- | --- | --- |
| Overview | CloudWatch when AWS is reachable, otherwise the in-process metric buffer + health/queue stores | Environment, version, readiness, traffic, backup, workers |
| Alerts | CloudWatch `DescribeAlarms` or derived local conditions | Acknowledge is audited; AWS console links are deep-links only |
| Workers | AI job store, redaction job store, notification deliveries | WhatsApp and content-safety rows stay `deployed: false` until those issues land |
| Errors | Grouped 5xx / job failures | Request/job ids only — no ticket text, contacts, OTPs, or images |
| Product | Aggregate ticket/notification counts | No citizen identifiers |

Municipality management lives at `/ops/municipalities` (issue #322). Only
developer operators can create profiles and the first municipality
administrator.

## API

All routes require `Authorization: Bearer` for a `developer_operator` session:

- `GET /v1/ops/overview`
- `GET /v1/ops/metrics`
- `GET /v1/ops/alerts`
- `POST /v1/ops/alerts/{alarmName}/ack`
- `GET /v1/ops/workers`
- `POST /v1/ops/workers/jobs/{jobId}/replay`
- `GET /v1/ops/errors`
- `GET /v1/ops/product`
- `GET /v1/ops/runbooks`
- `GET /v1/ops/municipalities`
- `POST /v1/ops/municipalities`
- `PUT /v1/ops/municipalities/{municipalityId}`
- `POST /v1/ops/municipalities/{municipalityId}/admin`
- `POST /v1/ops/municipalities/preview`
- `POST /v1/ops/tickets/{ticketId}/municipality/override`

Query filters are allowlisted (`range=1h|6h|24h|7d`, bounded `service`,
`severity`, `jobType`, UUID `municipalityId`). Unknown values return 400.

The browser never receives AWS credentials, raw CloudWatch Logs Insights, ticket
descriptions, photos, or presigned URLs.

## AWS permissions (API task role)

Least privilege, server-side only:

- `cloudwatch:GetMetricData`
- `cloudwatch:DescribeAlarms`
- `dynamodb:DescribeContinuousBackups` (backup status)

If those calls fail, the dashboard keeps working on application telemetry and
shows a fallback warning.

## Cardinality, retention, cost

- EMF series still use the single `env` dimension.
- High-cardinality fields stay on `metric_event` log lines (`path`, `version`,
  `request_id`, `job_id`).
- Error groups and operator acknowledgements are bounded (scan/list caps 200).
- Logs: 30 days hot in production (14 staging). Metrics: CloudWatch standard
  15 months. Operator audit rows follow DynamoDB PITR like other control tables.

## Staging drills

Keep using `python scripts/observability/staging_drill.py` for organic
CloudWatch alarm evaluation. After a drill, open `/ops` in staging as
`operator` and confirm the matching alarm row, request ids on the Errors tab,
and the runbook link.

## Safe recovery actions

- Replay is allowed only for dead-lettered `ai:` or `redaction:` jobs.
- Every replay and alert acknowledgement is written to `ops-audit`.
