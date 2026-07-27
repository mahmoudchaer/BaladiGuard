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
  window.localStorage.removeItem('baladiguard.staffSession');
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
      signedInAt: '2026-07-27T08:00:00Z',
    }),
  );
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
    vi.mocked(fetchTickets).mockResolvedValue([ticket]);
  });

  afterEach(() => {
    clearSession();
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
    expect(screen.getByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
  });

  it('keeps authenticated staff access after refresh through stored session state', async () => {
    signInSession();

    renderApp();

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'BaladiGuard staff login' }),
    ).not.toBeInTheDocument();
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
