# WhatsApp report submission channel (issue #296)

Deterministic guided WhatsApp Cloud API intake over the existing BaladiGuard backend.
This is **not** an AI chatbot.

## Status

Code lands with `WHATSAPP_PROVIDER=mock` so local/CI can exercise the full state machine
**without** a real Meta Business number. Production completion still requires:

1. Meta Cloud API app + approved WhatsApp number
2. Secrets in AWS Secrets Manager (`WHATSAPP_*`)
3. Public HTTPS webhook → deployed backend
4. Live end-to-end evidence (ticket in Dynamo/S3 + admin + same-phone OTP history)

## Architecture

```
Meta WhatsApp Cloud API
        │ HTTPS webhook (signed)
        ▼
GET/POST /v1/whatsapp/webhook
        │ verify signature + dedupe message id
        ▼
WhatsAppFlowEngine (deterministic FSM)
        ├── identity.reconcile_whatsapp_sender (phone claim, no session)
        ├── location.validate_location
        ├── photo_upload_service.upload_report_photo_bytes
        └── submission.submit_whatsapp_report → TicketService.submit_ticket
                ├── AI job queue
                └── image redaction queue
```

## Conversation states

`welcome → language → description → location → photo → optional_name → review → submitting → completed`

Also: `cancelled`, `expired`. Commands (deterministic): `help`, `back`, `cancel`, `restart`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `WHATSAPP_ENABLED` | Kill switch (`false` by default) |
| `WHATSAPP_PROVIDER` | `mock` (local/tests) or `cloud` (Meta Graph) |
| `WHATSAPP_PHONE_NUMBER_ID` | Approved WhatsApp phone-number id |
| `WHATSAPP_APP_SECRET` | `X-Hub-Signature-256` verification |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook subscription challenge |
| `WHATSAPP_ACCESS_TOKEN` | Graph send/media (required for `cloud`) |
| `WHATSAPP_GRAPH_API_VERSION` | Default `v21.0` |
| `WHATSAPP_CONVERSATION_TTL_HOURS` | Abandoned conversation expiry |
| `WHATSAPP_DEDUP_TTL_SECONDS` | Inbound message-id ledger TTL |

When `WHATSAPP_ENABLED=true`, startup/readiness fail closed if required secrets are missing.
Staging/production also require `WHATSAPP_PROVIDER=cloud`.

## DynamoDB tables

| Suffix | Key | TTL |
| --- | --- | --- |
| `whatsapp-conversations` | `conversationKey` = `{phoneNumberId}#{waId}` | `ttl` |
| `whatsapp-inbound-dedup` | `messageId` | `ttl` |

Created by `make db-migrate` / `python scripts/db/migrate.py`.

## Local mock testing

```bash
# backend/.env (never commit real secrets)
WHATSAPP_ENABLED=true
WHATSAPP_PROVIDER=mock
WHATSAPP_PHONE_NUMBER_ID=test-phone-id
WHATSAPP_APP_SECRET=test-app-secret
WHATSAPP_VERIFY_TOKEN=test-verify-token
```

Webhook verify:

```http
GET /v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=test-verify-token&hub.challenge=abc
```

Signed event fixtures are covered by `backend/tests/test_whatsapp_channel.py`.

## Production cutover (later)

1. Create Meta app + WhatsApp product; note phone-number id / app secret / verify token / access token.
2. Store secrets via `scripts/sync_env.py --push` (or Secrets Manager).
3. Deploy backend with `WHATSAPP_ENABLED=true` and `WHATSAPP_PROVIDER=cloud`.
4. Point Meta webhook to `https://<api-host>/v1/whatsapp/webhook` and subscribe to `messages`.
5. Run live: WhatsApp message → ticket → admin visibility → OTP history for same phone.
6. Attach completion evidence (no secrets / no citizen PII).

## Privacy

- Never log message bodies, phone numbers, media URLs, tokens, or tracking codes.
- Success receipts expose ticket number + status + optional deep link only.
- Typed phones inside chat are never treated as identity.
