import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/App';
import { config } from '@/services/config';
import {
  fetchTicketAggregates,
  fetchTicketMapViewport,
  fetchTickets,
  fetchTicketsPage,
} from '@/services/tickets';
import type { Ticket } from '@/types/ticket';
import type { TicketMapMarker } from '@/types/ticketCollection';
import { listStaffAccounts } from '@/services/staffAccounts';

vi.mock('@/services/tickets', () => ({
  fetchTickets: vi.fn(),
  fetchTicketsPage: vi.fn(),
  fetchTicketAggregates: vi.fn(),
  fetchTicketMapViewport: vi.fn(),
}));

vi.mock('@/services/staffAccounts', () => ({
  listStaffAccounts: vi.fn(),
  listStaffDepartments: vi.fn(async () => []),
  createStaffAccount: vi.fn(),
  updateStaffAccount: vi.fn(),
  setStaffAccountActive: vi.fn(),
}));

vi.mock('@/services/municipalities', () => ({
  listMunicipalities: vi.fn(async () => []),
  createMunicipality: vi.fn(),
  updateMunicipality: vi.fn(),
  provisionMunicipalityAdmin: vi.fn(),
  previewMunicipalityRouting: vi.fn(),
  overrideTicketMunicipality: vi.fn(),
}));

vi.mock('@/components/TicketMap', () => ({
  TicketMap: ({ markers, tickets }: { markers?: TicketMapMarker[]; tickets?: Ticket[] }) => (
    <div data-testid="ticket-map">Map with {markers?.length ?? tickets?.length ?? 0} pins</div>
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

function signInAdministratorSession() {
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'admin',
      name: 'Demo Administrator',
      staffId: 'staff_admin_001',
      role: 'administrator',
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      departmentIds: null,
      signedInAt: '2026-07-27T08:00:00Z',
      accessToken: 'test-admin-token',
    }),
  );
}

function signInOperatorSession() {
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'operator',
      name: 'Demo Developer Operator',
      staffId: 'staff_ops_001',
      role: 'developer_operator',
      municipalityId: null,
      departmentIds: null,
      signedInAt: '2026-08-19T08:00:00Z',
      accessToken: 'test-ops-token',
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
    vi.mocked(fetchTicketsPage).mockResolvedValue({
      items: [],
      tickets: [ticket],
      nextCursor: null,
      previousCursor: null,
      limit: 25,
      scannedCount: 1,
      approximateTotal: 1,
      freshnessHintSeconds: 30,
      fromCache: false,
    });
    vi.mocked(fetchTicketAggregates).mockResolvedValue({
      openCount: 1,
      criticalCount: 0,
      highCount: 1,
      unassignedCount: 1,
      overdueCount: 0,
      approximate: false,
    });
    vi.mocked(fetchTicketMapViewport).mockResolvedValue({
      markers: [
        {
          ticketId: ticket.ticketId,
          ticketNumber: ticket.ticketNumber,
          status: ticket.status,
          priority: ticket.priority,
          latitude: ticket.location.latitude,
          longitude: ticket.location.longitude,
          category: ticket.category,
        },
      ],
      clusters: [],
      limit: 200,
      truncated: false,
      zoom: 12,
    });
    vi.mocked(listStaffAccounts).mockResolvedValue([]);
  });

  afterEach(() => {
    installLocalStorage();
    clearSession();
    vi.unstubAllGlobals();
  });

  it('redirects unauthenticated users from the ticket list to login', () => {
    renderApp();

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    expect(fetchTicketsPage).not.toHaveBeenCalled();
  });

  it('redirects unauthenticated users from the map route to login', () => {
    renderApp('/map');

    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
    expect(fetchTicketMapViewport).not.toHaveBeenCalled();
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

  it('shows a busy sign-in control while staff authentication is in flight', async () => {
    if (config.useMockData) {
      return;
    }

    let resolveLogin: (value: Response) => void = () => undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveLogin = resolve;
          }),
      ),
    );
    const user = userEvent.setup();

    renderApp();

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.type(screen.getByLabelText('Password'), 'staff-demo-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(screen.getByRole('button', { name: 'Signing in…' })).toBeDisabled();

    resolveLogin(
      new Response(
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
      ),
    );

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
  });

  it('shows a reachable-service error when the staff login API is unreachable', async () => {
    if (config.useMockData) {
      return;
    }

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    const user = userEvent.setup();

    renderApp();

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.type(screen.getByLabelText('Password'), 'staff-demo-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to reach the staff authentication service.',
    );
    expect(window.localStorage.getItem('baladiguard.staffSession')).toBeNull();
    expect(screen.getByRole('heading', { name: 'BaladiGuard staff login' })).toBeInTheDocument();
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

  it('shows administrator navigation and renders the staff-account route', async () => {
    signInAdministratorSession();
    renderApp('/staff-accounts');
    expect(
      await screen.findByRole('heading', { name: 'Staff accounts', level: 2 }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Staff accounts' })).toBeInTheDocument();
  });

  it('shows operator navigation and renders the municipalities route', async () => {
    signInOperatorSession();
    renderApp('/ops/municipalities');
    expect(
      await screen.findByRole('heading', { name: 'Municipalities', level: 2 }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Municipalities' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Operations' })).not.toHaveAttribute('aria-current');
  });

  it('denies municipal staff who enter the staff-account URL directly', async () => {
    signInSession();
    renderApp('/staff-accounts');
    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Staff accounts' })).not.toBeInTheDocument();
    expect(listStaffAccounts).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(
      'You do not have access to that module. You were returned to your home page.',
    );
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

  it('exposes forgot-password entry and completes the reset form flow', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/v1/staff/password-reset/request')) {
        return new Response(
          JSON.stringify({
            message: 'If a matching staff account exists, a password reset code has been issued.',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      if (url.includes('/v1/staff/password-reset/confirm')) {
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          username?: string;
          code?: string;
          newPassword?: string;
        };
        expect(body.username).toBe('staff');
        expect(body.code).toBe('123456');
        expect(body.newPassword).toBe('new-staff-password-123');
        return new Response(
          JSON.stringify({ message: 'Password updated. Sign in with your new password.' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      throw new Error(`Unexpected fetch in password-reset test: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderApp('/login');

    await user.click(screen.getByRole('link', { name: 'Forgot password?' }));
    expect(await screen.findByRole('heading', { name: 'Forgot password' })).toBeInTheDocument();

    await user.type(screen.getByLabelText('Username'), 'staff');
    await user.click(screen.getByRole('button', { name: 'Request reset code' }));

    expect(await screen.findByRole('heading', { name: 'Reset password' })).toBeInTheDocument();
    expect(screen.getByLabelText('Username')).toHaveValue('staff');
    expect(screen.getByRole('status')).toHaveTextContent(
      'If a matching staff account exists, a password reset code has been issued.',
    );

    await user.type(screen.getByLabelText('Reset code'), '123456');
    await user.type(screen.getByLabelText('New password'), 'new-staff-password-123');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(
      await screen.findByRole('heading', { name: 'BaladiGuard staff login' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Password updated. Sign in with your new password.',
    );
    // Live API stubs fetch; mock mode short-circuits without network calls.
    if (!config.useMockData) {
      expect(fetchMock).toHaveBeenCalled();
    }
  });
});
