# Production security and abuse hardening (issue #316)

This is an engineering control set, not a penetration-test report or compliance
certification. It documents the backend-enforced bounds, rate policies, Host/CORS
assumptions, security headers, and incident steps that match the deployed API.

## Request bounds

| Control | Default | Where enforced |
| --- | --- | --- |
| JSON / non-upload write body | `MAX_JSON_BODY_BYTES` = 256 KiB | HTTP middleware (`Content-Length` + streamed byte count) |
| JSON object/array nesting | `MAX_JSON_NESTING_DEPTH` = 20 | HTTP middleware scans JSON text iteratively, then parses; `RecursionError` from the decoder is `400 PAYLOAD_TOO_NESTED`, not a 500 |
| Combined request headers | `MAX_HEADER_BYTES` = 16 KiB | HTTP middleware → `431 HEADERS_TOO_LARGE` |
| Report photo / work-order evidence | 5 MiB image + 256 KiB framing | `upload_abuse` before multipart parse |
| WhatsApp webhook | `WHATSAPP_MAX_WEBHOOK_BYTES` = 1 MiB | WhatsApp route (exempt from the JSON ceiling) |
| Municipality polygon | 4–256 vertices, `extra=forbid` | `GeoPolygon` |
| Merge duplicate IDs | 1–20 unique IDs | `MergeDuplicateTicketsRequest` |
| Workforce / staff department lists | ≤ 40 IDs | request schemas |
| Email fields | ≤ 254 chars | staff / municipality provision requests |
| Staff search / ticket list `q` | ≤ 80 chars | query params + `ticket_list_filters` |

Malformed `Content-Length`, oversized bodies, and unknown polygon keys are rejected
with bounded, non-sensitive error bodies (`VALIDATION_ERROR`, `PAYLOAD_TOO_LARGE`).
Handlers are not invoked after a size reject, so durable state is not partially
mutated.

## Authentication and authorization

Existing staff and citizen session models remain authoritative:

- Logged-out callers receive `401` on citizen and staff APIs (direct URL and API).
- Citizen sessions are server-stored hashes; phone-change and logout bump
  `sessionEpoch`. Staff deactivation / `revoke_staff_sessions` bump `session_epoch`.
- Municipality and department scope is enforced in `staff_can_access_ticket` and
  `staff_can_assign_department`. Developer-operator and municipal routes are
  mutually exclusive.
- Cookie-mode citizen writes require an `Origin` in the CORS allowlist.

Representative automated coverage lives in `test_staff_authorization.py`,
`test_citizen_account*.py`, `test_admin_staff_accounts_api.py`, and
`test_production_hardening.py`.

## Rate policies

See [rate-limiting-runbook.md](./rate-limiting-runbook.md). New #316 policies:

- `citizen-data-export` / `citizen-data-delete` — cost-aware profile export/delete
- `whatsapp-submission` — per canonical phone, before a *new* ticket + AI enqueue.
  Retries that already have a completed or recoverable `clientSubmissionKey`
  reuse the original ticket and do not consume another slot.
- `staff-mutation` — compromised-token write amplification
- `ops-dashboard` — CloudWatch/Dynamo scan cost on `/v1/ops/*`

Client identity still ignores forged `X-Forwarded-For` unless
`TRUST_X_FORWARDED_FOR=true` behind a gateway that overwrites the header.
Stored keys are HMAC fingerprints.

## Hosts, CORS, HTTPS, headers

- **CORS:** staging/production require explicit https, non-localhost
  `CORS_ALLOWED_ORIGINS` ([cors.py](../backend/app/core/cors.py)).
- **Trusted Host:** staging/production require `ALLOWED_HOSTS`. Terraform injects
  it from `var.api_domain_name` on every backend task (not Secrets Manager).
  Local/test default to `*` so TestClient (`Host: testserver`) works. `/health`,
  `/health/live`, and `/health/ready` are exempt so ALB probes that send the
  instance IP as `Host` do not fail the target group.
- **HTTPS:** TLS terminates at the load balancer / API Gateway. The API process
  does not redirect HTTP. Staging/production still emit HSTS on API responses.
- **API security headers:** `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store`, and HSTS
  in deployed environments.
- **SPA CSP:** citizen-web/admin static hosting owns Content-Security-Policy.
  This API serves JSON and does not set a page CSP.

`returnTo` allowlisting for citizen-web remains in `citizen-web/src/auth/returnTo.ts`.

## Uploads and user content

Photo upload still verifies decoded type, dimensions, animation, decompression
bombs, metadata stripping (re-encode), owner-scope object keys, presigned URL
TTL, and orphan claim state. See [photo-storage-security.md](./photo-storage-security.md).

User text is treated as untrusted in AI prompts (delimited citizen block +
allowlisted categories). DynamoDB access uses parameterized conditions.

## Incident response

| Symptom | First action | Owner |
| --- | --- | --- |
| Volumetric 429 spike | Tighten the named `RATE_LIMIT_*` policy; edge-block at WAF/API Gateway | On-call + developer operator |
| Suspected leaked staff token | `revoke_staff_sessions` or deactivate the account (bumps `session_epoch`) | Municipality admin / operator |
| Suspected leaked citizen session | Logout / phone-change path (bumps `sessionEpoch`) | Citizen or operator via support |
| Compromised `SECRET_KEY` | Rotate the secret and redeploy; existing staff tokens and rate-limit HMAC keys invalidate | Developer operator |
| WhatsApp submit flood | Tighten `RATE_LIMIT_WHATSAPP_SUBMIT_*`; Meta still signs webhooks | Operator |

Do not add a global “disable rate limits” switch.

## Residual material risks

| Risk | Why accepted | Owner |
| --- | --- | --- |
| Admin dashboard stores the staff Bearer token in `localStorage` | XSS in the admin bundle could exfiltrate a session. Citizen-web already supports httpOnly cookies; admin cookie sessions need a dedicated design. Compensating control: 12h staff token TTL + instant revocation. | Admin frontend follow-up |
| SPA Content-Security-Policy | Owned by CloudFront / static hosting, not this FastAPI process. | Deployment |
| Formal third-party pentest / compliance cert | Explicitly out of scope for #316. | Product / security program |
| Deeply nested JSON besides bounded `dict` fields | Body-size ceiling limits blast radius. `GeoPolygon` forbids extra keys and caps vertices. | Backend |

## Verification

```bash
cd backend
python -m pytest tests/test_production_hardening.py tests/test_shared_rate_limiting.py tests/test_cors.py tests/test_staff_authorization.py tests/test_photo_storage_security.py tests/test_upload_abuse_early.py -q
```
