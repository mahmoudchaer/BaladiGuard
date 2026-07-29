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
VITE_STAFF_USERNAME=staff
VITE_STAFF_PASSWORD=staff-demo-password
```

Mock fixtures remain available for explicit development and testing by setting
`VITE_USE_MOCK_DATA=true`. In mock mode, the dashboard loads tickets from the shared root fixture
`mock_tickets.json` and status changes are not persisted.

## Staff authentication

The Sprint 5 MVP protects the staff dashboard with a login screen. In mock mode
(`VITE_USE_MOCK_DATA=true`), credentials come from Vite env (`VITE_STAFF_USERNAME` /
`VITE_STAFF_PASSWORD`). Against the real API, the dashboard calls `POST /v1/staff/login`,
stores `{ username, signedInAt, accessToken }` in `localStorage`, and sends
`Authorization: Bearer <accessToken>` on staff ticket API requests. Logout clears the session.

Backend authorization (issue #72) rejects unauthenticated staff actions with `401 UNAUTHORIZED`.
Public citizen report submission and ticket tracking stay available without staff login.

Demo credentials (local/CI defaults):

```text
username: staff
password: staff-demo-password
```

These are temporary shared credentials, not production secrets. Rotate `SECRET_KEY` and the
backend staff password before any real deployment.

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
npm test
npm run typecheck
npm run build
```
