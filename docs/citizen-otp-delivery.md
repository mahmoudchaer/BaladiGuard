# Citizen OTP delivery channel (issue #297)

Configurable Plivo, WhatsApp, or SNS delivery for citizen one-time verification codes.
This is **independent** of ticket notifications (`NOTIFICATION_ADAPTER`) and of WhatsApp
report submission (#296).

## Channels

| `CITIZEN_OTP_DELIVERY_CHANNEL` | Behavior |
| --- | --- |
| unset (legacy) | `mock` when `NOTIFICATION_ADAPTER!=real` or `APP_ENV=test`; otherwise `sns` |
| `mock` | No provider call (local/CI). Codes via `peek_dev_otp_code` / optional stdout |
| `sns` | Amazon SNS SMS (existing path) |
| `whatsapp` | Meta Cloud API: approved **authentication template**, or sandbox `session_text` |
| `plivo` | Plivo SMS transport; BaladiGuard generates and checks the code |

`CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=session_text` is the agreed path for the Meta **test number**, which cannot create custom templates. It sends a free-form text OTP through the real Graph API and only works if:

- `NOTIFICATION_SANDBOX=true`
- the destination is on `NOTIFICATION_ALLOWLIST_PHONES`
- that WhatsApp user messaged the test business number within the last 24 hours

Production rejects `session_text` and still requires an approved authentication template. SNS remains the rollback (`CITIZEN_OTP_DELIVERY_CHANNEL=sns`).

## Plivo SMS (production candidate)

Set `CITIZEN_OTP_DELIVERY_CHANNEL=plivo` only after Plivo confirms the chosen sender and
route for Lebanon and real Alfa and touch tests succeed. Plivo is an SMS **transport**:
BaladiGuard generates a single six-digit code, stores only its HMAC hash, and remains the
authority that validates it. It retains purpose binding, single use, expiry, resend
supersession, login/change-phone authorization, and application rate limits.

```bash
CITIZEN_OTP_DELIVERY_CHANNEL=plivo
CITIZEN_OTP_PLIVO_AUTH_ID=...       # Secrets Manager/runtime only
CITIZEN_OTP_PLIVO_AUTH_TOKEN=...    # Secrets Manager/runtime only
CITIZEN_OTP_PLIVO_SOURCE=...        # approved sender ID/number supplied by Plivo
CITIZEN_OTP_PLIVO_TIMEOUT_SECONDS=10
```

The backend uses Plivo's Messages API with HTTP Basic authentication and one bounded request;
it does not retry automatically, because a timeout can mean the carrier send was accepted. No
credential, OTP, full destination, HTTP authorization header, or raw provider payload may be
logged. `plivo` has no automatic fallback to SNS/WhatsApp.

### Console setup and release gates

1. In **Plivo Console → Messaging → Geo Permissions**, enable Lebanon for SMS; leave all unused
   destinations disabled.
2. In **Plivo Console → Messaging → Sender IDs** (or with Plivo support if the console requires
   approval), configure the exact source allowed for Lebanon. Do not guess an alphanumeric sender.
3. In **Plivo Console → API Platform → API Credentials**, create or retrieve the Auth ID and Auth
   Token, then store them and the approved source only in AWS Secrets Manager/runtime configuration.
4. Deploy to staging and explicitly test an allowlisted real Alfa number and a real touch number:
   request OTP, enter it through the existing BaladiGuard endpoint, and confirm login/signup and
   change-phone flows. Record only masked numbers, status, timestamp, and safe metrics.

Do not regard a successful API response as proof of delivery or ownership. Review Plivo delivery
reports for `delivered`/failure evidence, but only successful BaladiGuard OTP verification proves
phone possession. CI mocks the HTTP boundary and never sends SMS. A funded/public-capable account
and successful Alfa/touch tests are production blockers.

For an opt-in paid live test, set the four runtime variables above and retain
`NOTIFICATION_SANDBOX=true` with only the operator-owned number in
`NOTIFICATION_ALLOWLIST_PHONES`. Use the deployed citizen UI/API; do not script or print the
OTP, token, or credentials. This procedure is intentionally not part of CI.

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

Sandbox allowlisting (`NOTIFICATION_SANDBOX` + `NOTIFICATION_ALLOWLIST_PHONES`) applies to all
real SMS/WhatsApp sends, including `plivo`.

## Template requirements

Meta must approve an **authentication / OTP** template whose body parameter is the
six-digit code. Recommended wording includes BaladiGuard, time limit, and “do not share”.
Optional URL/copy-code button may receive the same code parameter.

## Client UX

`POST /v1/citizen/auth/otp/request` returns `deliveryChannel`: `sms` | `whatsapp` | `dev`
so mobile/web can adapt copy. Verification remains `POST /v1/citizen/auth/otp/verify`.

## Rollback

Set `CITIZEN_OTP_DELIVERY_CHANNEL=sns`, `whatsapp`, or `mock` as appropriate and redeploy. No OTP hash, citizen, or session
migration required.

## Live completion (sandbox / test number)

1. Add tester phones in Meta API Setup and in `NOTIFICATION_ALLOWLIST_PHONES`.
2. Tester sends any message to the Meta test number (opens the 24h window).
3. Request OTP on citizen login with that same number.
4. Real Graph session text delivers the 6-digit code; verify as usual.

A future production cutover still needs an approved authentication template and `CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=template`. Mock-only demos are not this path.
