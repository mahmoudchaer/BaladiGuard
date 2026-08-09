# API documentation index

BaladiGuard API contracts and verification notes are maintained under `docs/`. The live machine-readable schema is served by FastAPI when the backend is running.

| Document | Purpose |
| --- | --- |
| [MVP_API_CONTRACT.md](./MVP_API_CONTRACT.md) | **Authoritative HTTP contract** — citizen/staff auth, tickets, locations, uploads, error envelope, enums |
| [privacy-lifecycle.md](./privacy-lifecycle.md) | Citizen export/delete and session revocation |
| [database.md](./database.md) | Persistence model aligned with the contract (memory + DynamoDB) |
| [notifications.md](./notifications.md) | Ticket lifecycle notify path (no public notification HTTP API) |
| [sprint6-testing.md](./sprint6-testing.md) | Sprint 6 auth/permission verification index |
| [configuration.md](./configuration.md) | Environment catalog (with [env-sync.md](./env-sync.md) for Secrets Manager pull/push) |

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
| Staff | Dashboard ticket list/detail, status/assignment mutations |
| Administrator | Elevated staff account operations (service layer; HTTP admin CRUD may be expanded later) |

Always prefer this contract + OpenAPI over informal client assumptions.
