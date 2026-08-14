# Citizen web (issue #263)

Responsive citizen-facing web app for public report browsing and possession-based
tracking. Separate from `admin/` (staff dashboard). Uses the same backend citizen-safe
contracts as the mobile app.

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

| Path                                        | Purpose                                           |
| ------------------------------------------- | ------------------------------------------------- |
| `/`                                         | Public report list (`GET /v1/tickets/public`)     |
| `/map`                                      | Public map + clustering (list alternative linked) |
| `/public/:ticketNumber`                     | Public detail                                     |
| `/track`                                    | Tracking-code lookup                              |
| `/privacy`                                  | Privacy copy for public projection                |
| `/login`, `/report`, `/history`, `/profile` | Stubs for authenticated follow-up                 |

## Configuration

| Variable             | Notes                                                       |
| -------------------- | ----------------------------------------------------------- |
| `VITE_APP_ENV`       | `local` / `development` / `test` / `staging` / `production` |
| `VITE_API_BASE_URL`  | Required https non-localhost in staging/production          |
| `VITE_USE_MOCK_DATA` | Local mock fixtures only                                    |
