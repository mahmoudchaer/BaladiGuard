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
| `staging` | Shared pre-production — **no silent localhost deep-link defaults** |
| `production` | Deployed environments — **no silent development defaults** |

Common short forms are normalized before checks: `prod` / `prd` → `production`,
`dev` / `develop` → `development`.

Unknown values fail validation and **abort startup** so a deploy typo cannot bypass
fail-closed rules.

## Policy

| Area | `local` / `development` / `test` | `staging` / `production` |
| --- | --- | --- |
| Persistence | `DATABASE_BACKEND=memory` allowed | Staging and production must use `dynamodb`. |
| Notifications | `NOTIFICATION_ADAPTER=mock` allowed | Staging and production must use the real adapter (staging may use provider sandbox/allowlists). |
| Secrets | Empty / placeholder `SECRET_KEY` allowed for local demos | Production: non-placeholder `SECRET_KEY` required |
| Staff auth password | Demo `STAFF_PASSWORD` allowed locally | Production: non-demo credentials required |
| Location | Empty `LOCATION_PLACE_INDEX_NAME` → local Beirut index | Production: real Amazon Location index required |
| Photo uploads | `AWS_S3_BUCKET` optional until you test uploads | Production: `AWS_S3_BUCKET` required |
| Dynamo endpoint | Localhost Docker URL allowed | Production must not point at localhost |
| Sample seed | Optional synthetic mocks only | Production: `SEED_SAMPLE_TICKETS=false` (never load real citizen exports) |
| Citizen deep links | Optional `CITIZEN_APP_BASE_URL` (defaults to `http://localhost:8081`) | **Required https**, non-localhost base for SMS/email links (#257) |

Backend **startup aborts** when `APP_ENV` is `production` or `staging` and validation
finds errors. In local / development / test, the process still starts and `/health`
reports `config.status`.

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
| `S3_PRESIGNED_URL_TTL_SECONDS` | No | `300` | Authorized photo URL lifetime; minimum 30 seconds |
| `DYNAMODB_ENDPOINT_URL` | No | empty = AWS | `http://localhost:8001` for Docker Local only |
| `DYNAMODB_TABLE_PREFIX` | No | `baladiguard-` | Table name prefix |
| `ACTIVITY_TIMELINE_USE_GSI` | No | `false` | Enable only after timeline GSIs are ACTIVE and `backfill_activity_timeline_keys.py` has finished for status, audit, and comments. See `docs/staff-comments-and-activity.md`. |
| `SEED_SAMPLE_TICKETS` | No | `false` | Must be `false` in production |
| `BEDROCK_MODEL_ID` | No | `amazon.nova-lite-v1:0` | AI classification / cleaning |
| `IMAGE_REDACTION_ENABLED` | No | `true` | Must remain enabled in staging/production. |
| `IMAGE_REDACTION_DETECTOR` | No | `aws_rekognition` | Deployed environments require Rekognition; disabled/local detectors are development-only. |
| `LOCATION_PLACE_INDEX_NAME` | Production | empty → local index | Geocoding |
| `AI_PROCESSING_CLAIM_TIMEOUT_SECONDS` | No | `300` | Integer ≥ 1 |
| `AI_JOB_MAX_ATTEMPTS` | No | `5` | Bounded attempts before dead-lettering |
| `AI_JOB_TIMEOUT_SECONDS` | No | `300` | Expired worker claims become eligible for recovery |
| `AI_JOB_BACKOFF_BASE_SECONDS` | No | `5` | First retry delay; later retries double |
| `AI_JOB_BACKOFF_MAX_SECONDS` | No | `300` | Upper bound for retry delay |
| `AI_JOB_POLL_SECONDS` | No | `1` | Idle worker polling interval |
| `DUPLICATE_DISTANCE_THRESHOLD_M` | No | `100` | Meters, ≥ 1 |
| `DUPLICATE_MIN_SCORE` | No | `0.4` | 0..1 |
| `DUPLICATE_SAME_CATEGORY_WEIGHT` | No | `1.0` | 0..1 |
| `DUPLICATE_SIMILAR_CATEGORY_WEIGHT` | No | `0.7` | 0..1 |
| `NOTIFICATION_ADAPTER` | Yes (prod: `real`) | `mock` | `mock` \| `real` (SES+SNS when real) |
| `SES_FROM_EMAIL` | Production (with real) | empty | Verified SES identity for ticket emails |
| `SES_CONFIGURATION_SET` | No | empty | Optional SES configuration set |
| `SNS_SMS_SENDER_ID` | No | empty | Optional SNS SMS sender id |
| `NOTIFICATION_ALLOW_SMS_ONLY_REAL` | No | `true` | Allow real SMS without SES from-address |
| `NOTIFICATION_SANDBOX` | No | `true` for local/test/development; else `false` | Restrict real sends to allowlists |
| `NOTIFICATION_ALLOWLIST_EMAILS` | Sandbox/testing | empty | Comma-separated allowlist |
| `NOTIFICATION_ALLOWLIST_PHONES` | Sandbox/testing | empty | Comma-separated E.164 allowlist |
| `NOTIFICATION_DESTINATION_RATE_LIMIT` | No | `10` | Per-destination burst cap |
| `NOTIFICATION_DESTINATION_RATE_WINDOW_SECONDS` | No | `60` | Throttle window (seconds) |
| `CITIZEN_APP_BASE_URL` | Staging + production | local/dev/test: `http://localhost:8081` when unset | Citizen app base for notification deep links (`/t/{trackingCode}`); staging/production must be https and non-localhost (#257) |
| `CORS_ALLOWED_ORIGINS` | Staging + production | local/dev/test: Vite admin `:5173`, citizen-web `:5174`, Expo ports when unset | Comma-separated browser origins for CORS (#263). Staging/production must set explicit https non-localhost origins (admin + citizen-web). |
| `OTP_DEV_PLAINTEXT_STDOUT` | Local only | `false` | **Unsafe local helper.** When `true` in `local`/`development`/`test`, citizen OTP codes are printed to process stdout (not the logging framework) so the mobile OTP flow can be completed without SMS. Default is off: use `CitizenService.peek_dev_otp_code` in tests, or enable this explicitly for manual local runs. Process stdout is often captured by Docker/IDE log collectors — never enable in staging/production. |
| `TRUST_X_FORWARDED_FOR` | No | `false` | Set `true` only behind a trusted proxy/gateway that strips or overwrites client-supplied XFF |
| `RATE_LIMIT_TICKET_SUBMIT_LIMIT` / `_WINDOW_SECONDS` | No | `20` / `60` | Public ticket submit (AI-triggering) |
| `RATE_LIMIT_TICKET_TRACK_LIMIT` / `_WINDOW_SECONDS` | No | `60` / `60` | Public tracking lookup |
| `RATE_LIMIT_UPLOAD_LIMIT` / `_WINDOW_SECONDS` | No | `10` / `60` | Report photo upload (stricter) |
| `RATE_LIMIT_LOCATION_VALIDATE_LIMIT` / `_WINDOW_SECONDS` | No | `30` / `60` | Location validate |
| `RATE_LIMIT_STAFF_LOGIN_LIMIT` / `_WINDOW_SECONDS` | No | `10` / `300` | Staff login |
| `RATE_LIMIT_STAFF_ASSISTANT_LIMIT` / `_WINDOW_SECONDS` | No | `30` / `60` | Staff assistant questions (#42) |
| `RATE_LIMIT_STAFF_SEARCH_LIMIT` / `_WINDOW_SECONDS` | No | `40` / `60` | Staff global search (#42 / #260) |
| `RATE_LIMIT_CITIZEN_OTP_REQUEST_*` / `RATE_LIMIT_CITIZEN_OTP_VERIFY_*` | No | `5`/`300`, `10`/`300` | Reserved for citizen OTP HTTP (#170) |
| `RATE_LIMIT_SMOKE_BYPASS_TOKEN` | No | empty | Optional smoke header token; never a global disable |
| `RATE_LIMIT_SMOKE_LIMIT` | No | `1000` | Higher still-enforced quota for smoke token clients |
| `SECRET_KEY` | Production | empty | Auth/signing; no placeholders in production |
| `SEED_DEMO_STAFF` | No | `true` for local/test/development; `false` for production | Bootstrap demo `admin`, `staff`, and `operator` accounts (#175 / #320) |
| `DEMO_STAFF_PASSWORD` | When seeding demos | `staff-demo-password` | Password used only to hash demo staff accounts; never used as shared login |
| `DEVELOPER_OPERATOR_USERNAME` / `DEVELOPER_OPERATOR_PASSWORD` | Production bootstrap | empty | Creates the first `developer_operator` if the username is unused (#320) |
| `DEVELOPER_OPERATOR_EMAIL` | With operator bootstrap | `ops@example.com` | Email on the bootstrapped operator account |
| `STAFF_PASSWORD` | Legacy alias | same as demo default | Deprecated alias for `DEMO_STAFF_PASSWORD` |
| `STAFF_USERNAME` | Legacy | `staff` | Deprecated; ignored for authentication |
| `STAFF_TOKEN_TTL_SECONDS` | No | `43200` | Integer ≥ 60 |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` |
| `LOG_FORMAT` | No | `text` | `text` \| `json` — use `json` in deployed environments (#185) |
| `APP_VERSION` | No | `0.1.0` | Deployed build label in structured logs and health payloads |
| `METRICS_EMF` | No | on when `APP_ENV=production` | `true` \| `false` — CloudWatch Embedded Metric Format on stdout |
| `READINESS_PROBE_PUBLISHER` | No | `true` | In-process `ReadyProbeSuccess` publisher for readiness alarms |
| `READINESS_PROBE_INTERVAL_SECONDS` | No | `30` | Publisher interval (≥ 5) |
| `OBSERVABILITY_ENV` | Apply script | `APP_ENV` / `production` | Stable CloudWatch `env` dimension for alarms/dashboard |
| `OBSERVABILITY_ALARM_ACTIONS` | Apply script | empty | Comma-separated SNS ARNs for `apply_observability.py --apply` |

Optional eval-only vars (`CLASSIFICATION_EVAL_*`, `OPENAI_API_KEY`) are documented in
`.env.example` and are not required for runtime.

Production observability (dashboards, alarms, retention, staging drill) is documented in
[production-observability.md](production-observability.md).

## Admin dashboard (`admin/`)

| Variable | Default | Notes |
| --- | --- | --- |
| `VITE_APP_ENV` | `local` | Staging/production enable fail-closed build validation. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Staging/production require an HTTPS non-localhost backend origin. |
| `VITE_USE_MOCK_DATA` | `false` | Opt-in mock fixtures |
| `VITE_STAFF_USERNAME` | `staff` | Local mock credential; must be absent from staging/production builds. |
| `VITE_STAFF_PASSWORD` | `staff-demo-password` | Local mock credential; must be absent from staging/production builds. |

Vite embeds these values in the browser bundle. They are not backend secrets.

## Citizen web (`citizen-web/`)

| Variable | Default | Notes |
| --- | --- | --- |
| `VITE_APP_ENV` | `local` | `local` \| `development` \| `test` \| `staging` \| `production` |
| `VITE_API_BASE_URL` | `http://localhost:8000` (local/dev/test only) | Staging/production **require** https non-localhost; never silent localhost |
| `VITE_USE_MOCK_DATA` | `false` | Local/dev mock fixtures only — rejected in staging/production |

Dev server defaults to port **5174** (admin uses 5173). Ensure backend `CORS_ALLOWED_ORIGINS` (or local defaults) include the citizen-web origin.

## Mobile (`mobile/`)

| Variable | Default | Notes |
| --- | --- | --- |
| `EXPO_PUBLIC_API_BASE_URL` | `http://localhost:8000/v1` | API base |
| `EXPO_PUBLIC_ENABLE_MOCK_API` | `false` | Opt-in mock submit |
| `EXPO_PUBLIC_APP_ENV` | `local` | App label |
| `EXPO_PUBLIC_CITIZEN_APP_HOST` | derived / placeholder | Host claimed for iOS Universal Links + Android App Links (`/t/*`); must match backend `CITIZEN_APP_BASE_URL` host (#257) |
| `EXPO_PUBLIC_CITIZEN_APP_BASE_URL` | empty | Optional full https base; used to derive host when `EXPO_PUBLIC_CITIZEN_APP_HOST` is unset |
| `EXPO_PUBLIC_SUPABASE_URL` | empty | Reserved / unused for MVP core path |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | empty | Reserved / unused for MVP core path |

## Local development (explicit)

1. Copy examples (or run `scripts/sync_env.py` — see [env-sync.md](env-sync.md)):

   ```bash
   copy backend\.env.example backend\.env
   copy .env.example .env
   copy admin\.env.example admin\.env
   copy citizen-web\.env.example citizen-web\.env
   copy mobile\.env.example mobile\.env
   ```

2. Keep `APP_ENV=local` (or omit it).
3. Prefer documented defaults: memory or DynamoDB Local for persistence, `NOTIFICATION_ADAPTER=mock`.
4. Start the API and confirm `/health` shows `"config": { "status": "ok", "issues": [] }`.

## Production checklist

Before deploy (#74):

1. `APP_ENV=production`
2. `DATABASE_BACKEND=dynamodb` with empty `DYNAMODB_ENDPOINT_URL` (real AWS)
3. `NOTIFICATION_ADAPTER=real` and `SES_FROM_EMAIL=<verified SES identity>`
4. After SES/SNS leave sandbox: `NOTIFICATION_SANDBOX=false` (and clear temporary allowlists)
5. Strong `SECRET_KEY` (not empty / not a placeholder)
6. Non-demo staff secrets (no demo `DEMO_STAFF_PASSWORD` in production)
7. `LOCATION_PLACE_INDEX_NAME=<Amazon Location index>`
8. `AWS_S3_BUCKET=<bucket>`
9. `SEED_SAMPLE_TICKETS=false`
10. `CITIZEN_APP_BASE_URL=https://…` (non-localhost; path for SMS/email `#257` deep links). Staging uses the same rule with `APP_ENV=staging`.
11. `CORS_ALLOWED_ORIGINS=https://admin…,https://citizen…` (explicit https non-localhost browser origins for admin + citizen-web, `#263`)
12. Admin production build: omit `VITE_STAFF_*`; browser-bundled credentials are mock-only
13. Citizen web production build: set `VITE_APP_ENV=production` and `VITE_API_BASE_URL=https://…` (never mock/localhost)
14. Confirm process starts (validation aborts on failure) and `/health` is `ok`
15. Mobile release: set `EXPO_PUBLIC_CITIZEN_APP_HOST` (or base URL) to the same host, rebuild so Associated Domains / App Links are baked in, and host AASA + Digital Asset Links JSON (see [notifications.md](./notifications.md#deep-links-257)).
16. Capacity / concurrency validation complete (see [release-readiness.md](./release-readiness.md) and [capacity-validation.md](./capacity-validation.md))

## Health payload

Distinct probes (#185):

- `GET /health/live` — process up only (always HTTP 200 when the app answers)
- `GET /health/ready` — database + config (HTTP 503 when not ready)
- `GET /health` — composite for humans/demos (HTTP 200; body may be `degraded`)

`GET /health` includes `config`, `ai`, `version`, and `probes`:

```json
{
  "status": "ok",
  "service": "baladiguard-api",
  "env": "local",
  "version": "0.1.0",
  "database": { "backend": "memory", "status": "ok" },
  "config": {
    "status": "ok",
    "issues": []
  },
  "ai": {
    "status": "ok",
    "pending": 0,
    "processing": 0,
    "failed": 0,
    "source": "memory_store",
    "backlogWarnThreshold": 25
  },
  "probes": {
    "liveness": "/health/live",
    "readiness": "/health/ready",
    "composite": "/health"
  }
}
```

Each issue has `code`, `message`, and `severity` only — never the configured secret value.
