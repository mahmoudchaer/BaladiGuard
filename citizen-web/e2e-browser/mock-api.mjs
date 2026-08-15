import http from 'node:http';

const PORT = Number(process.env.CITIZEN_WEB_E2E_API_PORT ?? 18080);
const ALLOWED_ORIGIN = process.env.CITIZEN_WEB_E2E_ORIGIN ?? 'http://127.0.0.1:4174';
const SESSION_COOKIE = 'citizen_session=e2e-session; Path=/v1; HttpOnly; SameSite=Lax';

const publicTicket = {
  ticketNumber: 'BG-100001',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  description: 'Large pothole near campus gate.',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  mapLocation: {
    addressText: 'Near AUB Main Gate, Beirut',
    latitude: 33.9,
    longitude: 35.482,
  },
  department: { name: 'Roads' },
  attribution: { displayName: 'Community member', isNamed: false },
  photoUrl: 'https://cdn.example/redacted.jpg',
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-02T12:00:00Z',
  imageObjectKey: 'reports/photos/v2/scope/original.jpg',
  imageUrl: 'https://private-media.example/original.jpg',
  publicImageObjectKey: 'reports/redacted/hidden-key.jpg',
  originalImageUrl: 'https://private-media.example/unredacted.jpg',
};

const trackFixture = {
  ticketNumber: 'BG-100001',
  trackingCode: 'ABC234',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  department: { name: 'Roads' },
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-02T12:00:00Z',
  lastUpdatedAt: '2026-08-02T12:00:00Z',
  timeline: [
    { status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' },
    { status: 'IN_PROGRESS', changedAt: '2026-08-02T12:00:00Z' },
  ],
  outcomeMessage: null,
};

const leakedResolvedTrackPayload = {
  ticketNumber: 'BG-100003',
  trackingCode: 'RES234',
  status: 'RESOLVED',
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  department: { name: 'Roads' },
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-04T12:00:00Z',
  lastUpdatedAt: '2026-08-04T12:00:00Z',
  timeline: [
    { status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' },
    { status: 'RESOLVED', changedAt: '2026-08-04T12:00:00Z' },
  ],
  outcomeMessage: 'The reported issue has been resolved.',
  ticketId: 'secret-ticket-id',
  resolutionReasonCode: 'WORK_COMPLETED',
  resolutionNote: 'Used the private crew address.',
  closureReasonCode: 'CONFIRMED_COMPLETE',
  closureNote: 'Internal close note',
  outcome: { code: 'WORK_COMPLETED', privateNote: 'do not show' },
};

const profileFixture = {
  userId: 'cit_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T00:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'SMS', announcements: false },
  publicNameVisible: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T00:00:00Z',
  updatedAt: '2026-08-01T00:00:00Z',
};

let session = false;

function send(response, status, body, extraHeaders = {}) {
  const headers = {
    'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
    'Access-Control-Allow-Credentials': 'true',
    'Access-Control-Allow-Headers':
      'Content-Type, X-Citizen-Session-Mode, X-Client-Version, Idempotency-Key',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, OPTIONS',
    'Cache-Control': 'no-store',
    ...extraHeaders,
  };
  if (body === null || body === undefined) {
    response.writeHead(status, headers);
    response.end();
    return;
  }
  headers['Content-Type'] = 'application/json';
  response.writeHead(status, headers);
  response.end(JSON.stringify(body));
}

function hasSession(request) {
  return (request.headers.cookie ?? '').includes('citizen_session=e2e-session');
}

const server = http.createServer((request, response) => {
  const url = new URL(request.url ?? '/', `http://127.0.0.1:${PORT}`);
  const method = (request.method ?? 'GET').toUpperCase();

  if (method === 'OPTIONS') {
    send(response, 204, null);
    return;
  }
  if (url.pathname === '/health') {
    send(response, 200, { ok: true });
    return;
  }

  if (url.pathname === '/v1/citizen/me' && method === 'GET') {
    if (!hasSession(request) && !session) {
      send(response, 401, { error: { code: 'UNAUTHORIZED' } });
      return;
    }
    send(response, 200, profileFixture);
    return;
  }
  if (url.pathname === '/v1/citizen/me' && method === 'PATCH') {
    send(response, 200, { ...profileFixture, fullName: 'Ada Updated' });
    return;
  }
  if (url.pathname === '/v1/citizen/auth/otp/request' && method === 'POST') {
    send(response, 202, { challengeId: 'chl_1', expiresIn: 300, message: 'Sent' });
    return;
  }
  if (url.pathname === '/v1/citizen/auth/otp/verify' && method === 'POST') {
    session = true;
    send(response, 200, profileFixture, { 'Set-Cookie': SESSION_COOKIE });
    return;
  }
  if (url.pathname === '/v1/citizen/auth/logout' && method === 'POST') {
    session = false;
    send(response, 204, null, {
      'Set-Cookie': 'citizen_session=; Path=/v1; Max-Age=0',
    });
    return;
  }
  if (url.pathname === '/v1/citizen/me/tickets' && method === 'GET') {
    send(response, 200, {
      items: [
        {
          trackingCode: 'ABC234',
          status: 'RESOLVED',
          category: 'road_damage',
          locationAddress: 'Near AUB Main Gate, Beirut',
          submittedAt: '2026-08-01T10:00:00Z',
          canSubmitResolutionFeedback: true,
          resolutionFeedbackStatus: null,
        },
      ],
      nextCursor: null,
      limit: 20,
    });
    return;
  }
  if (url.pathname === '/v1/tickets/public' && method === 'GET') {
    send(response, 200, { items: [publicTicket], nextCursor: null, limit: 20 });
    return;
  }
  if (url.pathname === '/v1/tickets/public/map' && method === 'GET') {
    send(response, 200, {
      markers: [
        {
          ticketNumber: 'BG-100001',
          status: 'IN_PROGRESS',
          category: 'road_damage',
          addressText: 'Near AUB Main Gate, Beirut',
          latitude: 33.9,
          longitude: 35.482,
        },
      ],
      clusters: [{ id: 'c1', latitude: 33.9, longitude: 35.482, count: 2 }],
      limit: 200,
      truncated: false,
      zoom: 15,
    });
    return;
  }
  if (url.pathname === '/v1/tickets/public/BG-100001' && method === 'GET') {
    send(response, 200, publicTicket);
    return;
  }
  if (url.pathname === '/v1/tickets/track/ABC234' && method === 'GET') {
    send(response, 200, trackFixture);
    return;
  }
  if (url.pathname === '/v1/tickets/track/RES234' && method === 'GET') {
    send(response, 200, leakedResolvedTrackPayload);
    return;
  }
  if (url.pathname === '/v1/tickets' && method === 'POST') {
    send(response, 201, {
      ticketId: 'tkt_1',
      ticketNumber: 'BG-100099',
      trackingCode: 'XYZ789',
      status: 'SUBMITTED',
      message: 'Report received.',
      createdAt: '2026-08-16T00:00:00Z',
    });
    return;
  }

  send(response, 404, { error: { message: `Unhandled ${method} ${url.pathname}` } });
});

server.listen(PORT, '127.0.0.1', () => {
  process.stdout.write(`citizen-web e2e API listening on 127.0.0.1:${PORT}\n`);
});
