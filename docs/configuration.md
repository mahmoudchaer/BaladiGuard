# Configuration (issue #147)

This is the **authoritative** catalog of BaladiGuard environment variables.
`.env.example` files mirror this document; when they disagree, update both.

Related work: staff dashboard auth (#71), health checks (#73), deployment (#74).

## Environments

Set `APP_ENV` (preferred) or `ENVIRONMENT` (alias).

| Value | Meaning |
| --- | --- |
| `local` | Default local development (documented soft defaults allowed) |
| `development` | Shared/dev servers (same soft defaults as local) |
| `test` | Automated tests / CI |
| `production` | Deployed environments — **no silent development defaults** |

Common short forms are normalized before checks: `prod` / `prd` → `production`,
`dev` / `develop` → `development`.

Unknown values (for example `staging`) fail validation and **abort startup** so a
deploy typo cannot bypass production fail-closed rules.

## Policy

| Area | `local` / `development` / `test` | `production` |
| --- | --- | --- |
| Persistence | `DATABASE_BACKEND=memory` allowed | Must be `dynamodb` |
| Notifications | `NOTIFICATION_ADAPTER=mock` allowed | Must be `real` |
| Secrets | Empty / placeholder `SECRET_KEY` allowed for local demos | Non-placeholder `SECRET_KEY` required |
| Staff auth password | Demo `STAFF_PASSWORD` allowed locally | Non-demo `STAFF_PASSWORD` required |
| Location | Empty `LOCATION_PLACE_INDEX_NAME` → local Beirut index | Real Amazon Location index required |
| Photo uploads | `AWS_S3_BUCKET` optional until you test uploads | `AWS_S3_BUCKET` required |
| Dynamo endpoint | Localhost Docker URL allowed | Must not point at localhost |
| Sample seed | Optional | `SEED_SAMPLE_TICKETS=false` |

Backend **startup aborts** when `APP_ENV=production` and validation finds errors.
In other environments, the process still starts and `/health` reports `config.status`.

Secret **values** are never printed in logs or returned by `/health`.

## Backend variables

| Variable | Required | Default (non-production) | Notes |
| --- | --- | --- | --- |
| `APP_ENV` / `ENVIRONMENT` | Recommended | `local` | See environments above |
| `DATABASE_BACKEND` | Yes (prod: `dynamodb`) | `memory` | `memory` \| `dynamodb` |
| `AWS_REGION` | Recommended | `us-east-1` | Used by DynamoDB / S3 / Bedrock |
| `AWS_ACCESS_KEY_ID` | When not using instance role | — | boto3 / uploads |
| `AWS_SECRET_ACCESS_KEY` | When not using instance role | — | Never commit |
| `AWS_S3_BUCKET` | Production | — | Photo uploads |
| `DYNAMODB_ENDPOINT_URL` | No | empty = AWS | `http://localhost:8001` for Docker Local only |
| `DYNAMODB_TABLE_PREFIX` | No | `baladiguard-` | Table name prefix |
| `SEED_SAMPLE_TICKETS` | No | `false` | Must be `false` in production |
| `BEDROCK_MODEL_ID` | No | `amazon.nova-lite-v1:0` | AI classification / cleaning |
| `LOCATION_PLACE_INDEX_NAME` | Production | empty → local index | Geocoding |
| `AI_PROCESSING_CLAIM_TIMEOUT_SECONDS` | No | `300` | Integer ≥ 1 |
| `DUPLICATE_DISTANCE_THRESHOLD_M` | No | `100` | Meters, ≥ 1 |
| `DUPLICATE_MIN_SCORE` | No | `0.4` | 0..1 |
| `DUPLICATE_SAME_CATEGORY_WEIGHT` | No | `1.0` | 0..1 |
| `DUPLICATE_SIMILAR_CATEGORY_WEIGHT` | No | `0.7` | 0..1 |
| `NOTIFICATION_ADAPTER` | Yes (prod: `real`) | `mock` | `mock` \| `real` |
| `TRUST_X_FORWARDED_FOR` | No | `false` | Set `true` only behind a trusted proxy/gateway that strips or overwrites client-supplied XFF |
| `RATE_LIMIT_TICKET_SUBMIT_LIMIT` / `_WINDOW_SECONDS` | No | `20` / `60` | Public ticket submit (AI-triggering) |
| `RATE_LIMIT_TICKET_TRACK_LIMIT` / `_WINDOW_SECONDS` | No | `60` / `60` | Public tracking lookup |
| `RATE_LIMIT_UPLOAD_LIMIT` / `_WINDOW_SECONDS` | No | `10` / `60` | Report photo upload (stricter) |
| `RATE_LIMIT_LOCATION_VALIDATE_LIMIT` / `_WINDOW_SECONDS` | No | `30` / `60` | Location validate |
| `RATE_LIMIT_STAFF_LOGIN_LIMIT` / `_WINDOW_SECONDS` | No | `10` / `300` | Staff login |
| `RATE_LIMIT_CITIZEN_OTP_REQUEST_*` / `RATE_LIMIT_CITIZEN_OTP_VERIFY_*` | No | `5`/`300`, `10`/`300` | Reserved for citizen OTP HTTP (#170) |
| `RATE_LIMIT_SMOKE_BYPASS_TOKEN` | No | empty | Optional smoke header token; never a global disable |
| `RATE_LIMIT_SMOKE_LIMIT` | No | `1000` | Higher still-enforced quota for smoke token clients |
| `SECRET_KEY` | Production | empty | Auth/signing; no placeholders in production |
| `SEED_DEMO_STAFF` | No | `true` for local/test/development; `false` for production | Bootstrap demo `admin` + `staff` accounts (#175) |
| `DEMO_STAFF_PASSWORD` | When seeding demos | `staff-demo-password` | Password used only to hash demo staff accounts; never used as shared login |
| `STAFF_PASSWORD` | Legacy alias | same as demo default | Deprecated alias for `DEMO_STAFF_PASSWORD` |
| `STAFF_USERNAME` | Legacy | `staff` | Deprecated; ignored for authentication |
| `STAFF_TOKEN_TTL_SECONDS` | No | `43200` | Integer ≥ 60 |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` |

Optional eval-only vars (`CLASSIFICATION_EVAL_*`, `OPENAI_API_KEY`) are documented in
`.env.example` and are not required for runtime.

## Admin dashboard (`admin/`)

| Variable | Default | Notes |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL |
| `VITE_USE_MOCK_DATA` | `false` | Opt-in mock fixtures |
| `VITE_STAFF_USERNAME` | `staff` | Demo credential for local #71 auth |
| `VITE_STAFF_PASSWORD` | `staff-demo-password` | **Local only** — never ship demo password to production builds |

Vite embeds these values in the browser bundle. They are not backend secrets.

## Mobile (`mobile/`)

| Variable | Default | Notes |
| --- | --- | --- |
| `EXPO_PUBLIC_API_BASE_URL` | `http://localhost:8000/v1` | API base |
| `EXPO_PUBLIC_ENABLE_MOCK_API` | `false` | Opt-in mock submit |
| `EXPO_PUBLIC_APP_ENV` | `local` | App label |
| `EXPO_PUBLIC_SUPABASE_URL` | empty | Reserved / unused for MVP core path |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | empty | Reserved / unused for MVP core path |

## Local development (explicit)

1. Copy examples (or run `scripts/sync_env.py` — see [env-sync.md](env-sync.md)):

   ```bash
   copy backend\.env.example backend\.env
   copy .env.example .env
   copy admin\.env.example admin\.env
   copy mobile\.env.example mobile\.env
   ```

2. Keep `APP_ENV=local` (or omit it).
3. Prefer documented defaults: memory or DynamoDB Local for persistence, `NOTIFICATION_ADAPTER=mock`.
4. Start the API and confirm `/health` shows `"config": { "status": "ok", "issues": [] }`.

## Production checklist

Before deploy (#74):

1. `APP_ENV=production`
2. `DATABASE_BACKEND=dynamodb` with empty `DYNAMODB_ENDPOINT_URL` (real AWS)
3. `NOTIFICATION_ADAPTER=real`
4. Strong `SECRET_KEY` (not empty / not a placeholder)
5. Non-demo `STAFF_PASSWORD` (not the local demo default)
6. `LOCATION_PLACE_INDEX_NAME=<Amazon Location index>`
7. `AWS_S3_BUCKET=<bucket>`
8. `SEED_SAMPLE_TICKETS=false`
9. Admin production build: set unique `VITE_STAFF_*` (not the demo password)
10. Confirm process starts (validation aborts on failure) and `/health` is `ok`

## Health payload

`GET /health` includes a `config` object:

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local",
  "database": { "backend": "memory", "status": "ok" },
  "config": {
    "status": "ok",
    "issues": []
  }
}
```

Each issue has `code`, `message`, and `severity` only — never the configured secret value.
