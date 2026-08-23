# Citizen OTP delivery channel (issue #297)

Configurable Twilio Verify, WhatsApp, or SNS delivery for citizen one-time verification codes.
This is **independent** of ticket notifications (`NOTIFICATION_ADAPTER`) and of WhatsApp
report submission (#296).

## Channels

| `CITIZEN_OTP_DELIVERY_CHANNEL` | Behavior |
| --- | --- |
| unset (legacy) | `mock` when `NOTIFICATION_ADAPTER!=real` or `APP_ENV=test`; otherwise `sns` |
| `mock` | No provider call (local/CI). Codes via `peek_dev_otp_code` / optional stdout |
| `sns` | Amazon SNS SMS (existing path) |
| `whatsapp` | Meta Cloud API: approved **authentication template**, or sandbox `session_text` |
| `twilio` | Twilio Verify v2 SMS; Twilio generates and checks the code |

`CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=session_text` is the agreed path for the Meta **test number**, which cannot create custom templates. It sends a free-form text OTP through the real Graph API and only works if:

- `NOTIFICATION_SANDBOX=true`
- the destination is on `NOTIFICATION_ALLOWLIST_PHONES`
- that WhatsApp user messaged the test business number within the last 24 hours

Production rejects `session_text` and still requires an approved authentication template. SNS remains the rollback (`CITIZEN_OTP_DELIVERY_CHANNEL=sns`).

## Twilio Verify (production target)

Set `CITIZEN_OTP_DELIVERY_CHANNEL=twilio` only after a real Verify Service and live
Lebanese carrier tests are complete. This is not a transport for a BaladiGuard-generated
code: Twilio Verify starts the verification and is the sole authority that may approve
the submitted code. BaladiGuard persists a purpose-bound, expiring, single-use challenge
without a local OTP hash, maintains its own IP/device/phone and attempt limits, and only
issues a session or transfers a phone claim after Verify returns `status=approved`.

```bash
CITIZEN_OTP_DELIVERY_CHANNEL=twilio
TWILIO_ACCOUNT_SID=...             # Secrets Manager/runtime only
TWILIO_API_KEY_SID=...             # production preferred Basic-auth username
TWILIO_API_KEY_SECRET=...          # Secrets Manager/runtime only
TWILIO_VERIFY_SERVICE_SID=...
TWILIO_VERIFY_TIMEOUT_SECONDS=10
```

Twilio documents API keys as its preferred production authentication method. `TWILIO_AUTH_TOKEN`
is accepted only for local troubleshooting; staging and production validation reject it in favor
of an API key pair. No Twilio credential, OTP, full destination, HTTP authorization header, or
raw provider payload may be logged. `twilio` has no automatic fallback to SNS/WhatsApp.

### Console setup and release gates

1. In **Twilio Console → Verify → Services**, create/select **BaladiGuard** and record only its
   `VA…` Service SID in the deployment secret reference.
2. In **Verify → Settings → Geo permissions**, search **Lebanon** and enable SMS as **Monitor all
   traffic for blocking fraud** (or allow traffic only after a documented risk decision), then save.
3. In **Verify → Services → BaladiGuard → SMS**, leave **Enable Fraud Guard** on. Review
   **Monitor → Insights → Verify → Fraud** and Verify Logs for safe operational evidence.
4. In **Console → Account → API keys & tokens**, create a production API key; store its SID,
   secret, Account SID, and Service SID only in AWS Secrets Manager/runtime configuration.
5. Deploy to staging and explicitly test an allowlisted real Alfa number and a real touch number:
   request OTP, enter it through the existing BaladiGuard endpoint, and confirm login/signup and
   change-phone flows. Record only masked numbers, status, timestamp, and safe metrics.

Trial accounts restrict recipients and expire; do not treat test credentials/magic numbers as a
Verify integration test. CI mocks the HTTP boundary and never sends SMS. A paid/public-capable
account and successful Alfa/touch tests are production blockers.

For an opt-in paid live test, set the four runtime variables above and
`BALADIGUARD_TWILIO_LIVE_TEST=1` in an operator shell, then use the deployed citizen UI/API with
an operator-owned +961 number. Do not script or print the OTP, token, or credentials; this
procedure is intentionally not part of CI.

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

Set `CITIZEN_OTP_DELIVERY_CHANNEL=sns`, `whatsapp`, or `mock` as appropriate and redeploy. No OTP hash, citizen, or session
migration required.

## Live completion (sandbox / test number)

1. Add tester phones in Meta API Setup and in `NOTIFICATION_ALLOWLIST_PHONES`.
2. Tester sends any message to the Meta test number (opens the 24h window).
3. Request OTP on citizen login with that same number.
4. Real Graph session text delivers the 6-digit code; verify as usual.

A future production cutover still needs an approved authentication template and `CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=template`. Mock-only demos are not this path.
