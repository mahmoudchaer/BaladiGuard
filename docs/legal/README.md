# Legal package (issue #321)

**Status:** product drafts prepared for owner and legal counsel review. These texts are **not** a certification of GDPR compliance or any other regulatory certification.

| Field | Value |
| --- | --- |
| Current package version | `2026-08-22` |
| Documents | `terms`, `privacy`, `acceptable-use` |
| Languages | `en`, `ar`, `fr` |
| Privacy contact | `privacy@baladiguard.app` |
| Intended age | 16+ |

## Layout

```
docs/legal/
  README.md
  en/{terms,privacy,acceptable-use}.md
  ar/{terms,privacy,acceptable-use}.md
  fr/{terms,privacy,acceptable-use}.md
```

Every document opens with a draft/review banner. Keep that banner when editing.

## Versioning

- Bump `CURRENT_LEGAL_VERSION` in `backend/app/services/legal/documents.py` when any document changes in a way that requires re-acceptance.
- Keep markdown filenames stable; version lives in the constant and in API catalog metadata.
- After a version bump, existing citizens see `legalAcceptanceRequired: true` on profile until they re-accept via OTP login or `POST /v1/citizen/me/legal-acceptance`.

## How clients load documents

| Client need | Endpoint |
| --- | --- |
| Catalog (ids, titles, version, languages) | `GET /v1/legal` |
| Full markdown body | `GET /v1/legal/{documentId}?lang=en\|ar\|fr` |
| Unsupported `lang` | Falls back to English |

The API resolves files from `docs/legal/{lang}/{documentId}.md` relative to the project root (or a parent of the backend working directory that contains `docs/legal`).

## Consent

Citizen OTP verify for `LOGIN_OR_SIGNUP` requires `acceptLegal: true` matching the current package version. Acceptance is stored on the citizen user as `legalAcceptance`.

## Related

- `docs/data-inventory.md` — data classes, purpose, retention, deletion
- `docs/privacy-lifecycle.md` — export, anonymize, TTL, privacy request handling
