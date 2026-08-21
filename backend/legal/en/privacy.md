> **Product draft — not a compliance certification.** This document is a product draft prepared for BaladiGuard owner and legal counsel review. It does not certify GDPR compliance or any other regulatory certification.

# Privacy Policy

**Version:** 2026-08-22  
**Contact:** privacy@baladiguard.app  
**Intended age:** 16+

## 1. Who processes your data

- **BaladiGuard platform operator** — citizen accounts, OTP authentication, sessions, platform logs, and product operations.
- **Participating municipalities** — municipal ticket records used for civic intake, routing, investigation, and resolution.

## 2. What we collect

| Data | Purpose |
| --- | --- |
| Verified phone number | Account identity, login (OTP), ticket ownership, SMS updates when enabled |
| Full name (optional) | Profile display and optional public attribution when you enable it |
| Email (optional) | Ticket updates / announcements only when you choose email delivery |
| Notification preferences | How we contact you about your reports |
| Legal acceptance record | Evidence that you accepted the current Terms, Privacy Policy, and Acceptable Use |
| Report content | Description, location, and photos needed to investigate and resolve issues |
| Contact snapshot on each ticket | Immutable copy at submission for operational follow-up |
| Session and OTP challenge records | Sign-in security; OTP uses keyed hashes only |
| Device / client metadata on submit | Abuse resistance and support diagnostics (not marketing) |
| WhatsApp channel messages (when used) | Conversational report intake for that channel |
| Moderation / AI processing outputs | Safety review and assisted classification for civic workflows |
| Operational logs | Reliability, security, and support |

We do not sell personal data. Citizen accounts do not use passwords.

## 3. Legal bases and consent

Account creation and login require acceptance of the current legal package (`acceptLegal` on OTP verify). Profile and re-acceptance endpoints record the same package version. Municipal processing of ticket records supports civic service delivery under participating municipality policies.

## 4. Retention (summary)

Authoritative detail lives in `docs/data-inventory.md` and `docs/privacy-lifecycle.md`. In short:

- Active citizen accounts: retained while active
- Anonymized citizen tombstones: retained for ownership/audit integrity with PII cleared
- Municipal tickets and contact snapshots: retained for municipal operations
- Citizen sessions: absolute ~30-day TTL
- OTP challenges: ~5-minute TTL
- Application logs: typically 30–90 days

## 5. Your controls

- View and update profile (`GET` / `PATCH /v1/citizen/me`)
- Export account and owned ticket summaries (`GET /v1/citizen/me/export`)
- Delete / anonymize account (`POST /v1/citizen/me/delete`)
- Re-accept updated legal terms (`POST /v1/citizen/me/legal-acceptance`)
- Control public name visibility (`publicNameVisible`, default off)

## 6. Sharing

Data is shared with participating municipalities as needed to handle reports, and with infrastructure processors (for example hosting, SMS/email, object storage) under operational contracts. We do not sell personal data.

## 7. International and security notes

Data may be processed in cloud regions configured for the deployment. We apply access controls, session revocation, and least-privilege staff scoping. No online service can guarantee absolute security.

## 8. Children

The Service is intended for users 16+. Do not use the Service if you are younger.

## 9. Contact and requests

privacy@baladiguard.app

Privacy requests may also be fulfilled through self-service export/delete or the documented manual ops path in `docs/privacy-lifecycle.md`.
