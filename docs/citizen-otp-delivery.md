# Citizen OTP delivery channel (issue #297)

Configurable WhatsApp (or SNS SMS) delivery for citizen one-time verification codes.
This is **independent** of ticket notifications (`NOTIFICATION_ADAPTER`) and of WhatsApp
report submission (#296).

## Channels

| `CITIZEN_OTP_DELIVERY_CHANNEL` | Behavior |
| --- | --- |
| unset (legacy) | `mock` when `NOTIFICATION_ADAPTER!=real` or `APP_ENV=test`; otherwise `sns` |
| `mock` | No provider call (local/CI). Codes via `peek_dev_otp_code` / optional stdout |
| `sns` | Amazon SNS SMS (existing path) |
| `whatsapp` | Meta Cloud API: approved **authentication template**, or sandbox `session_text` |

`CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=session_text` is the agreed path for the Meta **test number**, which cannot create custom templates. It sends a free-form text OTP through the real Graph API and only works if:

- `NOTIFICATION_SANDBOX=true`
- the destination is on `NOTIFICATION_ALLOWLIST_PHONES`
- that WhatsApp user messaged the test business number within the last 24 hours

Production rejects `session_text` and still requires an approved authentication template. SNS remains the rollback (`CITIZEN_OTP_DELIVERY_CHANNEL=sns`).

Exactly one channel is used per OTP request. There is **no** automatic WhatsApp→SNS fallback.

## Configuration

```bash
# Deliberate switch — do not reuse NOTIFICATION_ADAPTER for this.
CITIZEN_OTP_DELIVERY_CHANNEL=whatsapp

CITIZEN_OTP_WHATSAPP_PHONE_NUMBER_ID=...
CITIZEN_OTP_WHATSAPP_ACCESS_TOKEN=...   # Secrets Manager only
CITIZEN_OTP_WHATSAPP_TEMPLATE_NAME=baladiguard_auth_otp
CITIZEN_OTP_WHATSAPP_TEMPLATE_LANGUAGE=en
CITIZEN_OTP_WHATSAPP_GRAPH_API_VERSION=v21.0
# CITIZEN_OTP_WHATSAPP_TEMPLATE_BUTTON_INDEX=0   # or none/off to omit button component
# CITIZEN_OTP_WHATSAPP_TIMEOUT_SECONDS=15
# CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=session_text  # Meta test number; tester must message first
```

When `session_text` is selected, a template name is not required. Staging may use it with `NOTIFICATION_SANDBOX=true`. Production rejects it.

Sandbox allowlisting (`NOTIFICATION_SANDBOX` + `NOTIFICATION_ALLOWLIST_PHONES`) still
applies to both `sns` and `whatsapp` real sends.

## Template requirements

Meta must approve an **authentication / OTP** template whose body parameter is the
six-digit code. Recommended wording includes BaladiGuard, time limit, and “do not share”.
Optional URL/copy-code button may receive the same code parameter.

## Client UX

`POST /v1/citizen/auth/otp/request` returns `deliveryChannel`: `sms` | `whatsapp` | `dev`
so mobile/web can adapt copy. Verification remains `POST /v1/citizen/auth/otp/verify`.

## Rollback

Set `CITIZEN_OTP_DELIVERY_CHANNEL=sns` and redeploy. No OTP hash, citizen, or session
migration required.

## Live completion (sandbox / test number)

1. Add tester phones in Meta API Setup and in `NOTIFICATION_ALLOWLIST_PHONES`.
2. Tester sends any message to the Meta test number (opens the 24h window).
3. Request OTP on citizen login with that same number.
4. Real Graph session text delivers the 6-digit code; verify as usual.

A future production cutover still needs an approved authentication template and `CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=template`. Mock-only demos are not this path.
