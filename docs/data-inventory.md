# Data inventory (authoritative — issue #321)

This inventory lists BaladiGuard MVP data classes, purposes, retention, and deletion behavior. It complements `docs/privacy-lifecycle.md` and the legal package under `docs/legal/` (version `2026-08-22`).

> Product draft prepared for owner/legal counsel review — not a GDPR/compliance certification.

**Privacy contact:** privacy@baladiguard.app  
**Intended age:** 16+

## Controllers

| Controller | Scope |
| --- | --- |
| BaladiGuard platform operator | Citizen accounts, OTP/auth, sessions, platform logs, product ops |
| Participating municipalities | Municipal ticket records for civic operations |

## Inventory

| Data class | Examples | Purpose | Retention (MVP) | Deletion / anonymization |
| --- | --- | --- | --- | --- |
| Citizen accounts | `userId`, phone, optional name/email, notification prefs, `legalAcceptance` | Identity, login, ownership, consent evidence | While active | `POST /v1/citizen/me/delete` clears PII, releases phone claim, clears `legalAcceptance`, sets `active=false`, keeps tombstone |
| Citizen sessions | Opaque session id, token hash, `ttl` | Keep signed-in; revoke on logout/phone change/delete | Absolute ~30 days; DynamoDB TTL on `ttl` | Immediate revoke; TTL purge |
| OTP challenges | Challenge id, phone, purpose, code hash, `ttl` | Phone verification | ~5 minutes; DynamoDB TTL on `ttl` | Consumed/superseded then TTL |
| Legal acceptance | Package versions + `acceptedAt`, locale, source | Consent to current Terms/Privacy/AUP | With account | Cleared on anonymize; re-accept on version bump |
| Staff accounts | Username, password hash, role, scope | Municipal/platform work | While employed / active | Admin deactivate; no citizen PII |
| Tickets (municipal) | Status, category, location, description, photo key, `ownerUserId`, municipality/department | Civic intake and resolution | Municipal ops; target ≥ 7 years or lawful disposal | Not erased on citizen delete; owner id retained |
| Ticket contact snapshots | Submission-time name/phone/email/channel | Immutable ops follow-up | With ticket | Not rewritten by profile edits or citizen anonymize |
| Report photos | S3 object keys under reports | Evidence for investigation | With ticket; noncurrent versions 90 days | Follow backup/lifecycle runbooks |
| WhatsApp channel | Conversation state, inbound message ids | Conversational intake | Conversation + dedup TTL | Channel-specific TTL; no marketing use |
| AI / moderation outputs | Classification, content-safety, redaction jobs | Assist routing and safety | Operational job retention | Jobs expire/complete; not a citizen directory |
| Notifications / delivery ledger | Ticket-linked delivery attempts | Delivery audit | Up to ~90 days | Prefer ticket id over raw PII in logs |
| Ticket submission claims | Idempotency keys | Retry safety | ~14 days completed; short reclaim window | DynamoDB TTL |
| Ticket audit / status history | Actor ids, action types | Municipal workflow integrity | With ticket | Retained after citizen anonymize |
| Application logs | Request ids, path groups, errors | Reliability and security | 30–90 days in sink | No OTP plaintext/tokens; prefer ids over phone/email |
| Ops / privacy request audit | Export/delete/manual privacy actions | Accountability for privacy handling | Operational retention | Developer-ops readable; documented manual path |
| Backups | DynamoDB PITR, S3 versions | Disaster recovery | Per AWS config / photo noncurrent 90 days | Isolated restores only |
| Test / demo fixtures | Synthetic phones/emails | Local/CI demos | N/A in production | Never copy production exports into repo |

## Consent linkage

- OTP verify (`LOGIN_OR_SIGNUP`) requires `acceptLegal: true` for package `2026-08-22`.
- Profile exposes `legalAcceptance` and `legalAcceptanceRequired`.
- Re-accept: `POST /v1/citizen/me/legal-acceptance`.
- Public documents: `GET /v1/legal`, `GET /v1/legal/{documentId}?lang=en|ar|fr`.

## Related

- `docs/legal/README.md`
- `docs/privacy-lifecycle.md`
- `docs/database.md`
- `docs/production-backup-restore.md`
