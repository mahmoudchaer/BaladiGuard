# Citizen ticket notifications

Issue #317 replaces the legacy single SMS/email selector with server-authoritative,
independent mobile push, email, and WhatsApp preferences. OTP and account-security
delivery are separate and cannot be disabled here. Existing `SMS` selections migrate
to WhatsApp; the legacy `ticketUpdates` field remains in responses during rollout and
is not used to silently send ordinary SMS.

Preferences are global per citizen. Per-ticket overrides are intentionally not
supported in this iteration: a global model avoids ambiguous partial subscriptions
and keeps history/detail consistent across web and mobile. Event switches cover report
receipt, status changes, work updates, resolutions/reopens, and action requests.

Mobile devices register through `PUT /v1/citizen/me/push-devices` and unregister with
`DELETE /v1/citizen/me/push-devices/{deviceId}`. Registrations are app-environment
scoped, support multiple devices, and are removed with account deletion because they
are stored inside the citizen record. The mobile client unregisters its device when
push is disabled. Invalid Expo tokens are recorded as permanent failures and can be
cleaned up by the delivery maintenance worker without retry storms.

Production email uses SES, WhatsApp uses an approved Meta template, and push uses the
Expo Push API. Provider callbacks are telemetry only. Delivery idempotency remains
owned by the notification claim ledger; transient failures release claims for bounded
worker retry while permanent failures retain them.
