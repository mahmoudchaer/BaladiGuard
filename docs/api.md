# API documentation index

BaladiGuard API contracts and verification notes are maintained under `docs/`. The live machine-readable schema is served by FastAPI when the backend is running.

| Document | Purpose |
| --- | --- |
| [MVP_API_CONTRACT.md](./MVP_API_CONTRACT.md) | **Authoritative HTTP contract** — citizen/staff auth, tickets, locations, uploads, error envelope, enums |
| [privacy-lifecycle.md](./privacy-lifecycle.md) | Citizen export/delete and session revocation |
| [image-redaction.md](./image-redaction.md) | Private-original/public-derivative image redaction contract and runbook |
| [database.md](./database.md) | Persistence model aligned with the contract (memory + DynamoDB) |
| [notifications.md](./notifications.md) | Ticket lifecycle notify path (no public notification HTTP API) |
| [sprint6-mvp-acceptance.md](./sprint6-mvp-acceptance.md) | Sprint 6 full-flow acceptance checklist and demo path (#49) |
| [sprint6-testing.md](./sprint6-testing.md) | Sprint 6 auth/permission verification index |
| [configuration.md](./configuration.md) | Environment catalog (with [env-sync.md](./env-sync.md) for Secrets Manager pull/push) |
| [workforce.md](./workforce.md) | Municipality workers, teams, ticket assignment, and workload (#245) |
| [work-orders.md](./work-orders.md) | Maintenance work orders and structured resolution/rejection reasons (#247) |

## Interactive OpenAPI

With the API running:

```text
GET /docs          # Swagger UI
GET /openapi.json  # OpenAPI document
GET /health        # Liveness + safe config status
```

Default local base URL: `http://localhost:8000`.

## Auth surface (Sprint 6 summary)

| Layer | Access |
| --- | --- |
| Public | Health, public reports browse, tracking codes, location validate (rate-limited) |
| Contribution-ready citizen | Submit tickets, upload report photos, account/me routes per contract |
| Staff | Dashboard ticket list/detail, status/assignment mutations, workforce list/assign/workload |
| Administrator | Staff-account administration and workforce directory create/edit/deactivate |

Always prefer this contract + OpenAPI over informal client assumptions.
