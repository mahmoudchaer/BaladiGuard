# Rate limiting & abuse protection runbook (issue #186)

## Overview

BaladiGuard enforces aligned fixed-window rate limits on abuse-sensitive HTTP routes.

Public photo upload (`POST /v1/uploads/report-photo`) is additionally guarded in HTTP
middleware **before** `call_next` / multipart parsing: a `Content-Length` ceiling
(5MB file + framing allowance) and the upload rate-limit policy both short-circuit so
bursty or oversized bodies are not spooled into `UploadFile`.

Counters are:

- **In-memory** when `DATABASE_BACKEND=memory` (local/CI).
- **Shared DynamoDB** table `{prefix}rate-limit-buckets` when `DATABASE_BACKEND=dynamodb`
  (multi-instance safe across workers and deployments).

Edge controls (API Gateway usage plans / WAF IP sets) remain recommended defense-in-depth when
the production edge is available; the DynamoDB limiter is the in-repo multi-instance guarantee.

## Policies

| Policy name | Default | Typical route |
| --- | --- | --- |
| `public-ticket-submission` | 20 / 60s | `POST /v1/tickets` (AI intake) |
| `public-ticket-tracking` | 60 / 60s | `GET /v1/tickets/track/{code}` |
| `public-upload-report-photo` | 10 / 60s | `POST /v1/uploads/report-photo` |
| `public-location-validate` | 30 / 60s | `POST /v1/locations/validate` |
| `staff-login` | 10 / 300s | `POST /v1/staff/login` |
| `staff-password-reset-request` | 10 / 300s (shares staff-login knobs) | `POST /v1/staff/password-reset/request` |
| `staff-password-reset-confirm` | max(staff-login, 20) / 300s | `POST /v1/staff/password-reset/confirm` |
| `citizen-otp-request` | 5 / 300s | Citizen OTP request |
| `citizen-otp-verify` | 10 / 300s | Citizen OTP verify |
| `citizen-data-export` | 5 / 300s | `GET /v1/citizen/me/export` |
| `citizen-data-delete` | 3 / 300s | `POST /v1/citizen/me/delete` |
| `whatsapp-submission` | 8 / 3600s | WhatsApp ticket submit (per canonical phone) |
| `staff-mutation` | 300 / 60s | Authenticated staff writes (tickets, work orders, workforce, admin) |
| `ops-dashboard` | 120 / 60s | `/v1/ops/*` developer dashboard |

Tune via `RATE_LIMIT_*` environment variables (see `docs/configuration.md`). Invalid values
fail config validation.

## Client identity

- Default: use the direct TCP peer (`request.client.host`). Forged `X-Forwarded-For` is ignored.
- `TRUST_X_FORWARDED_FOR=true`: use the leftmost XFF hop **only** when a trusted proxy/API
  Gateway overwrites client-supplied values. Malformed hops fall back to the direct peer.
- Stored / logged keys are HMAC-SHA256 fingerprints (prefix only in logs). Raw IPs, phones, and
  usernames are not written by the limiter.

## Rejection shape

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42
```

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please wait before trying again.",
    "details": [],
    "requestId": "req_..."
  }
}
```

Challenge-scoped citizen OTP and staff password-reset attempt exhaustion also use
`RATE_LIMIT_EXCEEDED` (same client-facing code as the IP/edge HTTP limiter) so agents can
treat all 429s uniformly.

## Observability

Rejected requests emit a structured warning:

`rate_limit_exceeded policy=... retry_after=... client_key_fp=... request_id=...`

Aggregate on `policy` and `request_id`. Do not log or export raw client identities.

## Smoke / deploy checks

Set a strong `RATE_LIMIT_SMOKE_BYPASS_TOKEN` in the deploy environment. Smoke clients send:

`X-BaladiGuard-Smoke-Token: <token>`

That path uses a higher `RATE_LIMIT_SMOKE_LIMIT` quota under a distinct policy name suffix
(`:smoke`). It **does not** disable protection globally and does not raise quotas for other
clients.

Staff/admin authenticated ticket APIs use the generous `staff-mutation` ceiling so a
compromised token cannot amplify merges, work-order creation, or AI-adjacent writes.
Do not turn off rate limiting to make dashboards work.

## Tuning

1. Identify the hot policy from logs (`policy=`).
2. Adjust the matching `RATE_LIMIT_*_LIMIT` / `*_WINDOW_SECONDS`.
3. Redeploy / refresh task environment. DynamoDB windows align on epoch boundaries, so a new
   window starts cleanly after `window_seconds`.
4. Prefer tightening upload and ticket-submit first under abuse; loosen tracking only if
   legitimate citizen polling is affected.

## Emergency blocking

Options, in order of preference:

1. **Tighten limits** for the abused policy (for example set upload/submit to `1` temporarily).
2. **Edge block** the offending source at API Gateway/WAF/security group (preferred for volumetric attacks).
3. **Rotate** `SECRET_KEY` only if client-key hashing must invalidate historical bucket keys
   (rarely needed for emergency IP blocks).

**Do not** set a global “disable rate limits” flag. There is intentionally no such switch.

## Local verification

```bash
cd backend
python -m pytest tests/test_public_ticket_abuse_protection.py tests/test_shared_rate_limiting.py tests/test_production_hardening.py -q
```
