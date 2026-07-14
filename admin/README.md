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

By default the dashboard talks to the local backend at `http://localhost:8000`.
Start the backend and local database first, then run the admin dashboard:

```bash
cd ../backend
uvicorn app.main:app --reload
```

Follow the database setup in `docs/local-database-setup.md` when you need persisted local state.

## Environment variables

Create `admin/.env.local` if needed:

```env
VITE_USE_MOCK_DATA=false
VITE_API_BASE_URL=http://localhost:8000
```

Mock fixtures remain available for explicit development and testing by setting
`VITE_USE_MOCK_DATA=true`. In mock mode, the dashboard loads tickets from the shared root fixture
`mock_tickets.json` and status changes are not persisted.

## Status update verification

To confirm the dashboard is using the real backend endpoint:

1. Start the backend and admin dashboard with `VITE_USE_MOCK_DATA=false`.
2. Open a ticket detail page in the admin dashboard.
3. Change the workflow status.
4. Confirm the browser network request is `PATCH /v1/tickets/{ticketId}/status`.
5. Refresh the ticket detail page and confirm the updated status remains visible.

Backend validation errors, failed requests, and invalid status transitions appear below the status
selector.

## Quality checks

```bash
npm run lint
npm run format:check
npm run typecheck
npm run build
```
