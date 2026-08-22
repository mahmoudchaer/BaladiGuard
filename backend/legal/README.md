# Packaged legal documents (backend image)

Runtime source for `GET /v1/legal`. The backend Docker context is `backend/`,
so these files are copied to `/app/legal` and must stay here.

Keep this tree in sync with `docs/legal/{en,ar,fr}/`. Bump
`CURRENT_LEGAL_VERSION` in `app/services/legal/documents.py` when acceptance
must be renewed.
