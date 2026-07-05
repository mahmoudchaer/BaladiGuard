# BaladiGuard Admin Dashboard

Web dashboard for municipality staff to review and manage submitted infrastructure tickets.

## Stack

- React 19 + TypeScript
- Vite

## Local development

```bash
cd admin
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

By default the dashboard loads tickets from the shared root fixture `mock_tickets.json`.

## Environment variables

Create `admin/.env.local` if needed:

```env
VITE_USE_MOCK_DATA=true
VITE_API_BASE_URL=http://localhost:8000
```

Set `VITE_USE_MOCK_DATA=false` once `GET /v1/tickets` is available.

## Quality checks

```bash
npm run lint
npm run format:check
npm run typecheck
npm run build
```
