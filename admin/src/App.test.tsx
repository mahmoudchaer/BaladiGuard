import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/App';
import { fetchTickets } from '@/services/tickets';
import type { Ticket } from '@/types/ticket';

vi.mock('@/services/tickets', () => ({
  fetchTickets: vi.fn(),
}));

vi.mock('@/components/TicketMap', () => ({
  TicketMap: ({ tickets }: { tickets: Ticket[] }) => (
    <div data-testid="ticket-map">Map with {tickets.length} pins</div>
  ),
}));

const ticket: Ticket = {
  ticketId: 'tkt_123',
  ticketNumber: 'BG-2026-0001',
  trackingCode: 'ABC123',
  description: 'Large pothole near the university gate.',
  contact: {},
  location: {
    latitude: 33.896,
    longitude: 35.478,
    addressText: 'Hamra, Beirut',
    source: 'GPS',
  },
  imageObjectKey: 'reports/tkt_123.jpg',
  status: 'UNDER_REVIEW',
  category: 'road_damage',
  priority: 'high',
  createdBy: null,
  municipalityId: null,
  departmentId: null,
  duplicateGroupId: null,
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:01:00Z',
};

function clearSession() {
  window.localStorage?.removeItem('baladiguard.staffSession');
}

function installLocalStorage() {
  const store = new Map<string, string>();

  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => {
        store.clear();
      },
    },
  });
}

function signInSession() {
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'staff',
      name: 'Demo Municipal Staff',
      staffId: 'staff_muni_001',
      role: 'municipal_staff',
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      departmentIds: ['d1111111-1111-1111-1111-111111111111'],
      signedInAt: '2026-07-27T08:00:00Z',
      accessToken: 'test-staff-token',
    }),
  );
}

function stubStaffLoginFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (!url.includes('/v1/staff/login')) {
        throw new Error(`Unexpected fetch in App auth tests: ${url}`);
      }

      const body = JSON.parse(String(init?.body ?? '{}')) as {
        username?: string;
        password?: string;
      };

      if (body.username === 'staff' && body.password === 'staff-demo-password') {
        return new Response(
          JSON.stringify({
            accessToken: 'test-staff-token',
            tokenType: 'Bearer',
            staffId: 'staff_muni_001',
            username: 'staff',
            name: 'Demo Municipal Staff',
            role: 'municipal_staff',
            municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            departmentIds: ['d1111111-1111-1111-1111-111111111111'],
            expiresIn: 43200,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }

      return new Response(
        JSON.stringify({
          error: {
            code: 'UNAUTHORIZED',
            message: 'Invalid staff username or password.',
            details: [],
            requestId: 'req_test',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      );
    }),
  );
}

function corruptSession(session: unknown) {
  window.localStorage.setItem('baladiguard.staffSession', JSON.stringify(session));
}

function renderApp(route = '/') {
  window.history.pushState({}, 'Test page', route);
  return render(<App />);
}

describe('App staff authentication', () => {
  beforeEach(() => {
    installLocalStorage();
    vi.clearAllMocks();
    clearSession();
    stubStaffLoginFetch();
    vi.mocked(fetchTickets).mockResolvedValue([ticket]);
  });

  afterEach(() => {
    installLocalStorage();
    clearSession();
    vi.unstubAllGlobals();
  });

  it('redirects unauthenticated users from the ticket list to login', () => {
    renderApp();

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    expect(fetchTickets).not.toHaveBeenCalled();
  });

  it('redirects unauthenticated users from the map route to login', () => {
    renderApp('/map');

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    expect(fetchTickets).not.toHaveBeenCalled();
  });

  it('redirects unauthenticated users from ticket details to login', () => {
    renderApp('/tickets/tkt_123');

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
  });

  it('shows an authentication failure without logging credentials', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const consoleLog = vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const user = userEvent.setup();

    renderApp();

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Invalid staff username or password.',
    );
    expect(window.localStorage.getItem('baladiguard.staffSession')).toBeNull();
    expect(consoleError).not.toHaveBeenCalled();
    expect(consoleLog).not.toHaveBeenCalled();

    consoleError.mockRestore();
    consoleLog.mockRestore();
  });

  it('lets staff sign in and returns to the requested protected route', async () => {
    const user = userEvent.setup();

    renderApp('/map');

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.type(screen.getByLabelText('Password'), 'staff-demo-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('heading', { name: 'Map View' })).toBeInTheDocument();
    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
  });

  it('preserves the requested route search and hash after sign in', async () => {
    const user = userEvent.setup();

    renderApp('/map?status=open#north');

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.type(screen.getByLabelText('Password'), 'staff-demo-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('heading', { name: 'Map View' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/map');
    expect(window.location.search).toBe('?status=open');
    expect(window.location.hash).toBe('#north');
  });

  it('keeps authenticated staff access after refresh through stored session state', async () => {
    signInSession();

    renderApp();

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'BaladiGuard staff login' }),
    ).not.toBeInTheDocument();
  });

  it('clears corrupt stored sessions with non-string fields', () => {
    corruptSession({
      username: 123,
      signedInAt: '2026-07-27T08:00:00Z',
    });

    renderApp();

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    expect(window.localStorage.getItem('baladiguard.staffSession')).toBeNull();
  });

  it('clears corrupt stored sessions missing an access token', () => {
    corruptSession({
      username: 'staff',
      signedInAt: '2026-07-27T08:00:00Z',
    });

    renderApp();

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    expect(window.localStorage.getItem('baladiguard.staffSession')).toBeNull();
  });

  it('fails login when browser storage is unavailable', async () => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: null,
    });
    const user = userEvent.setup();

    renderApp();

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.type(screen.getByLabelText('Password'), 'staff-demo-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to create a staff session in this browser.',
    );
    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
  });

  it('logs staff out, clears the session, and returns to login', async () => {
    const user = userEvent.setup();
    signInSession();

    renderApp();

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    });
    expect(window.localStorage.getItem('baladiguard.staffSession')).toBeNull();
  });
});
