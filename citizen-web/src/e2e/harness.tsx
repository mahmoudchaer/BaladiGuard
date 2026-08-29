import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { AppRoutes } from '@/App';
import {
  historyFixture,
  profileFixture,
  publicListFixture,
  publicMapFixture,
  publicTicketFixture,
  leakedResolvedTrackPayload,
  submitFixture,
  trackFixture,
} from '@/contracts/fixtures';

if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:test';
}
if (typeof URL.revokeObjectURL !== 'function') {
  URL.revokeObjectURL = () => undefined;
}

function pathname(input: RequestInfo | URL): string {
  return new URL(String(input), 'http://localhost:8000').pathname;
}

export function installControlledBackend(authenticated = false) {
  let session = authenticated;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = pathname(input);
    const method = (init?.method ?? 'GET').toUpperCase();

    if (path === '/v1/citizen/me' && method === 'GET') {
      return session
        ? new Response(JSON.stringify(profileFixture), { status: 200 })
        : new Response(JSON.stringify({ error: { code: 'UNAUTHORIZED' } }), { status: 401 });
    }
    if (path === '/v1/citizen/me' && method === 'PATCH') {
      return new Response(JSON.stringify({ ...profileFixture, fullName: 'Ada Updated' }), {
        status: 200,
      });
    }
    if (path === '/v1/citizen/auth/otp/request' && method === 'POST') {
      return new Response(
        JSON.stringify({ challengeId: 'chl_1', expiresIn: 300, message: 'Sent' }),
        { status: 202 },
      );
    }
    if (path === '/v1/citizen/auth/otp/verify' && method === 'POST') {
      session = true;
      return new Response(JSON.stringify(profileFixture), { status: 200 });
    }
    if (path === '/v1/citizen/auth/logout' && method === 'POST') {
      session = false;
      return new Response(null, { status: 204 });
    }
    if (path === '/v1/citizen/me/tickets' && method === 'GET') {
      return new Response(JSON.stringify(historyFixture), { status: 200 });
    }
    if (path === '/v1/citizen/me/rewards' && method === 'GET') {
      return new Response(
        JSON.stringify({
          ruleVersion: 'rewards-v1',
          confirmedPoints: 0,
          pendingPoints: 0,
          monthlyPoints: 0,
          monthlyPeriod: '2026-08',
          levelId: 'neighbor',
          levelTitle: 'Neighbor',
          nextLevelId: 'helper',
          nextLevelTitle: 'Helper',
          pointsToNextLevel: 25,
          badges: [],
          privateRankAllTime: null,
          privateRankMonthly: null,
          publicRankAllTime: null,
          publicRankMonthly: null,
          participation: {
            optedIn: false,
            publicNameVisible: false,
            hasDisplayName: true,
            eligible: false,
            missing: ['leaderboardOptIn', 'publicNameVisible'],
          },
          recentEvents: [],
          recognitionOnly: true,
        }),
        { status: 200 },
      );
    }
    if (path === '/v1/rewards/leaderboard' && method === 'GET') {
      return new Response(
        JSON.stringify({
          period: 'all-time',
          periodKey: 'all-time',
          items: [],
          nextCursor: null,
          limit: 20,
          ruleVersion: 'rewards-v1',
          recognitionOnly: true,
        }),
        { status: 200 },
      );
    }
    if (path.endsWith('/resolution-feedback') && method === 'POST') {
      return new Response(JSON.stringify({ canSubmit: false, status: 'CONFIRMED_FIXED' }), {
        status: 200,
      });
    }
    if (path === '/v1/tickets/public' && method === 'GET') {
      return new Response(JSON.stringify(publicListFixture), { status: 200 });
    }
    if (path === '/v1/tickets/public/map' && method === 'GET') {
      return new Response(JSON.stringify(publicMapFixture), { status: 200 });
    }
    if (path === '/v1/tickets/public/BG-100001' && method === 'GET') {
      return new Response(JSON.stringify(publicTicketFixture), { status: 200 });
    }
    if (path === '/v1/tickets/track/ABC234' && method === 'GET') {
      return new Response(JSON.stringify(trackFixture), { status: 200 });
    }
    if (path === '/v1/tickets/track/RES234' && method === 'GET') {
      return new Response(JSON.stringify(leakedResolvedTrackPayload), { status: 200 });
    }
    if (path === '/v1/locations/validate' && method === 'POST') {
      return new Response(
        JSON.stringify({
          success: true,
          location: {
            latitude: 33.9,
            longitude: 35.5,
            addressText: 'Hamra, Beirut',
            source: 'MANUAL',
          },
        }),
        { status: 200 },
      );
    }
    if (path === '/v1/uploads/report-photo' && method === 'POST') {
      return new Response(JSON.stringify({ imageObjectKey: 'reports/private/photo.jpg' }), {
        status: 200,
      });
    }
    if (path === '/v1/tickets' && method === 'POST') {
      return new Response(JSON.stringify(submitFixture), { status: 201 });
    }

    return new Response(JSON.stringify({ error: { message: `Unhandled ${method} ${path}` } }), {
      status: 404,
    });
  });

  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

export function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}
