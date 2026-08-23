# Citizen OTP delivery channel (issue #297)

Configurable Firebase Phone Auth, WhatsApp, or SNS delivery for citizen one-time verification codes.
This is **independent** of ticket notifications (`NOTIFICATION_ADAPTER`) and of WhatsApp
report submission (#296).

## Channels

| `CITIZEN_OTP_DELIVERY_CHANNEL` | Behavior |
| --- | --- |
| unset (legacy) | `mock` when `NOTIFICATION_ADAPTER!=real` or `APP_ENV=test`; otherwise `sns` |
| `mock` | No provider call (local/CI). Codes via `peek_dev_otp_code` / optional stdout |
| `sns` | Amazon SNS SMS (existing path) |
| `whatsapp` | Meta Cloud API: approved **authentication template**, or sandbox `session_text` |
| `firebase` | Firebase Phone Auth; Firebase generates/checks the code, then the backend verifies its signed ID token |

`CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=session_text` is the agreed path for the Meta **test number**, which cannot create custom templates. It sends a free-form text OTP through the real Graph API and only works if:

- `NOTIFICATION_SANDBOX=true`
- the destination is on `NOTIFICATION_ALLOWLIST_PHONES`
- that WhatsApp user messaged the test business number within the last 24 hours

Production rejects `session_text` and still requires an approved authentication template. SNS remains the rollback (`CITIZEN_OTP_DELIVERY_CHANNEL=sns`).

## Firebase Phone Auth (production candidate)

Set `CITIZEN_OTP_DELIVERY_CHANNEL=firebase` only after Firebase Phone Auth is enabled,
Firebase SMS Region Policy allows only Lebanon, and real Alfa/touch tests succeed. Firebase
generates and checks the user-visible code. BaladiGuard first creates a rate-limited,
purpose-bound `firebase` challenge through the existing OTP-request endpoint; the official
web/mobile SDK then completes Firebase's challenge and sends a Firebase ID token plus that opaque
challenge ID to BaladiGuard. The backend validates the token's signature, audience, phone-provider
claim, and E.164 phone claim before atomically consuming the matching challenge and completing the
existing login/signup or change-phone workflow. Firebase challenges have no locally generated code
or OTP hash.

```bash
CITIZEN_OTP_DELIVERY_CHANNEL=firebase
FIREBASE_PROJECT_ID=your-firebase-project-id
```

The Firebase web configuration is public build configuration, but must still be managed as runtime
configuration rather than hard-coded. No Firebase ID token, OTP, full destination, or raw provider
payload may be logged. `firebase` has no automatic fallback to SNS/WhatsApp.

### Console setup and release gates

1. In **Firebase Console → Authentication → Sign-in method**, enable **Phone**.
2. In **Authentication → Settings → SMS region policy**, choose **Allow** and select only
   **Lebanon (LB)**.
3. In **Authentication → Settings → Authorized domains**, add every deployed citizen-web hostname;
   local development uses a separate Firebase project/domain policy.
4. Configure the web app with the Firebase Console values through its runtime build environment.
5. Deploy to staging and explicitly test an operator-owned real Alfa number and a real touch number:
   request OTP in the Firebase-enabled client, enter it there, then confirm BaladiGuard login/signup
   and change-phone flows. Record only masked numbers, status, timestamp, and safe metrics.

Do not regard an SMS send response as proof of ownership. Only the Firebase-approved, server-
verified ID token counts. CI mocks token verification and never sends SMS. Firebase’s current
billing/quota requirements and successful Alfa/touch tests are production blockers.

For an opt-in live test, use an operator-owned number, preserve BaladiGuard request/verification
rate limits, and do not script or print the OTP or Firebase ID token. This procedure is not part of
CI.

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

Sandbox allowlisting (`NOTIFICATION_SANDBOX` + `NOTIFICATION_ALLOWLIST_PHONES`) applies to SNS and
WhatsApp. Firebase separately enforces its configured SMS Region Policy and anti-abuse controls.

## Template requirements

Meta must approve an **authentication / OTP** template whose body parameter is the
six-digit code. Recommended wording includes BaladiGuard, time limit, and “do not share”.
Optional URL/copy-code button may receive the same code parameter.

## Client UX

`POST /v1/citizen/auth/otp/request` returns `deliveryChannel`: `sms` | `whatsapp` | `dev`
so mobile/web can adapt copy. For Firebase, the web/mobile SDK sends and verifies the code after
that request, then calls `POST /v1/citizen/auth/firebase/complete`; legacy providers continue to
use `POST /v1/citizen/auth/otp/verify`. Citizens see “SMS,” never a provider name.

## Rollback

Set `CITIZEN_OTP_DELIVERY_CHANNEL=sns`, `whatsapp`, or `mock` as appropriate and redeploy. No OTP hash, citizen, or session
migration required.

## Live completion (sandbox / test number)

1. Add tester phones in Meta API Setup and in `NOTIFICATION_ALLOWLIST_PHONES`.
2. Tester sends any message to the Meta test number (opens the 24h window).
3. Request OTP on citizen login with that same number.
4. Real Graph session text delivers the 6-digit code; verify as usual.

A future production cutover still needs an approved authentication template and `CITIZEN_OTP_WHATSAPP_MESSAGE_MODE=template`. Mock-only demos are not this path.
