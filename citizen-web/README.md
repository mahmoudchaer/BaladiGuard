# Citizen web (issue #263)

Responsive citizen-facing web app for public browsing, secure phone-OTP accounts,
profiles, report contribution, drafts/retry, and account-linked history. Separate from
`admin/` (staff dashboard). Uses the same backend citizen-safe contracts as mobile.

## Setup

```bash
cd citizen-web
npm ci
copy .env.example .env
npm run dev
```

Dev server: http://localhost:5174

Backend local CORS defaults already include this origin. For staging/production, set
`CORS_ALLOWED_ORIGINS` on the API (see `docs/configuration.md`).

## Commands

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

## Routes

| Path                    | Purpose                                           |
| ----------------------- | ------------------------------------------------- |
| `/`                     | Public landing page; does not fetch report data   |
| `/reports`              | Six-item paginated public report directory        |
| `/map`                  | Public map + clustering (list alternative linked) |
| `/public/:ticketNumber` | Public detail                                     |
| `/track`                | Tracking-code lookup                              |
| `/privacy`              | Privacy copy for public projection                |
| `/login`                | Phone OTP sign-in/create-account flow             |
| `/report`               | Guest draft/location; OTP required before submit  |
| `/history`              | Protected paginated account-linked report history |
| `/profile`              | Protected optional profile and phone-change flow  |

## Browser session security

Citizen web opts into the existing opaque citizen session through
`X-Citizen-Session-Mode: cookie` on OTP verification. The API puts the opaque token in
a `Secure` (staging/production), `HttpOnly`, `SameSite=Lax` cookie scoped to `/v1` and
omits it from the browser response. The frontend sends requests with browser
credentials and never stores a bearer token in localStorage, sessionStorage, or
IndexedDB.

Cookie-authenticated mutations are accepted only when `Origin` matches the backend's
explicit `CORS_ALLOWED_ORIGINS` allowlist. Production should serve the API and citizen
web from the same registrable HTTPS site so `SameSite=Lax` remains effective. Mobile
continues using the unchanged Bearer-token response and platform secure storage.

Authenticated report drafts are account-scoped in IndexedDB. A guest draft expires after
24 hours; a recent one is migrated to the verified account after OTP and then removed from
the guest slot. Drafts contain supported form state,
the stable idempotency key, and an already-uploaded safe object reference when a
partial submission succeeds; they never contain authentication material. A selected
local photo may need to be selected again after a browser restart.

## Configuration

| Variable             | Notes                                                       |
| -------------------- | ----------------------------------------------------------- |
| `VITE_APP_ENV`       | `local` / `development` / `test` / `staging` / `production` |
| `VITE_API_BASE_URL`  | Required https non-localhost in staging/production          |
| `VITE_USE_MOCK_DATA` | Local mock fixtures only                                    |
