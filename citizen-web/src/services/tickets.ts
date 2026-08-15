import { config } from '@/services/config';
import type {
  CitizenTicketResponse,
  PublicTicketListResponse,
  PublicTicketMapViewportResponse,
  PublicTicketResponse,
} from '@/types/ticket';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

export const TRACK_LOOKUP_NOT_FOUND_MESSAGE =
  "We couldn't find a report with that tracking code. Check the code and try again.";
export const TRACK_LOOKUP_INVALID_MESSAGE =
  'That tracking code is not valid. Use the 6-character code from your submission confirmation.';
export const TRACK_LOOKUP_NETWORK_MESSAGE =
  'Unable to look up that report right now. Please try again.';
export const PUBLIC_TICKETS_NETWORK_MESSAGE =
  'Unable to load public reports right now. Check your connection and try again.';
export const PUBLIC_TICKET_NOT_FOUND_MESSAGE =
  'We could not find that public report. It may have been unpublished or the link is incorrect.';
export const PUBLIC_TICKET_NETWORK_MESSAGE =
  'Unable to load that public report right now. Check your connection and try again.';

type PublicTicketListOptions = {
  limit?: number;
  cursor?: string | null;
  q?: string;
  status?: string;
  category?: string;
  signal?: AbortSignal;
};

export type PublicMapViewport = {
  north: number;
  south: number;
  east: number;
  west: number;
  zoom: number;
};

function apiUrl(path: string): string {
  return `${config.apiBaseUrl}/v1${path.startsWith('/') ? path : `/${path}`}`;
}

function isOfflineError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    error.name === 'TypeError' ||
    message.includes('network') ||
    message.includes('failed to fetch') ||
    message.includes('network request failed')
  );
}

async function parseApiError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { message?: string; detail?: string };
    if (typeof body.message === 'string' && body.message.trim()) {
      // Prefer fixed citizen copy for public surfaces — only use generic fallback.
      return fallback;
    }
  } catch {
    // ignore
  }
  return fallback;
}

/** Strip any accidental sensitive keys if a mock or misconfigured proxy leaks them. */
export function sanitizePublicTicket(raw: PublicTicketResponse): PublicTicketResponse {
  return {
    ticketNumber: String(raw.ticketNumber ?? ''),
    status: raw.status,
    category: raw.category ?? null,
    description: String(raw.description ?? ''),
    location: { addressText: String(raw.location?.addressText ?? '') },
    mapLocation: {
      addressText: String(raw.mapLocation?.addressText ?? raw.location?.addressText ?? ''),
      latitude: Number(raw.mapLocation?.latitude),
      longitude: Number(raw.mapLocation?.longitude),
    },
    department: raw.department?.name ? { name: raw.department.name } : null,
    attribution: {
      displayName: String(raw.attribution?.displayName ?? 'Community member'),
      isNamed: Boolean(raw.attribution?.isNamed),
    },
    photoUrl: raw.photoUrl ?? null,
    createdAt: String(raw.createdAt ?? ''),
    updatedAt: raw.updatedAt ?? null,
  };
}

export async function getPublicTickets({
  limit = 20,
  cursor,
  q,
  status,
  category,
  signal,
}: PublicTicketListOptions = {}): Promise<PublicTicketListResponse> {
  if (config.useMockData) {
    return getPublicTicketsMock({ limit });
  }

  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.set('cursor', cursor);
  }
  if (q?.trim()) params.set('q', q.trim());
  if (status) params.set('status', status);
  if (category) params.set('category', category);

  let response: Response;
  try {
    response = await fetch(apiUrl(`/tickets/public?${params.toString()}`), {
      method: 'GET',
      signal,
    });
  } catch (error) {
    if (isOfflineError(error)) {
      throw new Error(PUBLIC_TICKETS_NETWORK_MESSAGE, { cause: error });
    }
    throw error;
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response, PUBLIC_TICKETS_NETWORK_MESSAGE));
  }

  const body = (await response.json()) as PublicTicketListResponse;
  return {
    items: (body.items ?? []).map(sanitizePublicTicket),
    nextCursor: body.nextCursor ?? null,
    limit: body.limit ?? limit,
  };
}

export async function getPublicMapViewport(
  viewport: PublicMapViewport,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<PublicTicketMapViewportResponse> {
  const limit = options.limit ?? 200;
  const params = new URLSearchParams({
    north: String(viewport.north),
    south: String(viewport.south),
    east: String(viewport.east),
    west: String(viewport.west),
    zoom: String(viewport.zoom),
    limit: String(limit),
  });

  if (config.useMockData) {
    const reports = getPublicTicketsMock({ limit }).items;
    return {
      markers: reports.map((report) => ({
        ticketNumber: report.ticketNumber,
        status: report.status,
        category: report.category,
        addressText: report.mapLocation.addressText,
        latitude: report.mapLocation.latitude,
        longitude: report.mapLocation.longitude,
      })),
      clusters: [],
      limit,
      truncated: false,
      zoom: viewport.zoom,
    };
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(`/tickets/public/map?${params.toString()}`), {
      method: 'GET',
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    if (isOfflineError(error)) {
      throw new Error(PUBLIC_TICKETS_NETWORK_MESSAGE, { cause: error });
    }
    throw error;
  }
  if (!response.ok) {
    throw new Error(await parseApiError(response, PUBLIC_TICKETS_NETWORK_MESSAGE));
  }
  const body = (await response.json()) as PublicTicketMapViewportResponse;
  return {
    markers: body.markers ?? [],
    clusters: body.clusters ?? [],
    limit: body.limit ?? limit,
    truncated: Boolean(body.truncated),
    zoom: body.zoom ?? viewport.zoom,
  };
}

export async function getPublicTicketByNumber(ticketNumber: string): Promise<PublicTicketResponse> {
  const normalized = ticketNumber.trim().toUpperCase();
  if (!normalized) {
    throw new Error(PUBLIC_TICKET_NOT_FOUND_MESSAGE);
  }

  if (config.useMockData) {
    return getPublicTicketByNumberMock(normalized);
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(`/tickets/public/${encodeURIComponent(normalized)}`), {
      method: 'GET',
    });
  } catch (error) {
    if (isOfflineError(error)) {
      throw new Error(PUBLIC_TICKET_NETWORK_MESSAGE, { cause: error });
    }
    throw error;
  }

  if (response.status === 404) {
    throw new Error(PUBLIC_TICKET_NOT_FOUND_MESSAGE);
  }
  if (!response.ok) {
    throw new Error(await parseApiError(response, PUBLIC_TICKET_NETWORK_MESSAGE));
  }

  return sanitizePublicTicket((await response.json()) as PublicTicketResponse);
}

/** Strip staff-only keys if a misconfigured proxy leaks them onto tracking. */
export function sanitizeCitizenTicket(raw: CitizenTicketResponse): CitizenTicketResponse {
  return {
    ticketNumber: raw.ticketNumber ?? null,
    trackingCode: String(raw.trackingCode ?? ''),
    status: raw.status,
    category: raw.category ?? null,
    location: raw.location?.addressText ? { addressText: String(raw.location.addressText) } : null,
    department: raw.department?.name ? { name: raw.department.name } : null,
    createdAt: String(raw.createdAt ?? ''),
    updatedAt: raw.updatedAt ?? null,
    lastUpdatedAt: String(raw.lastUpdatedAt ?? raw.updatedAt ?? raw.createdAt ?? ''),
    timeline: (raw.timeline ?? []).map((entry) => ({
      status: entry.status,
      changedAt: String(entry.changedAt ?? ''),
    })),
  };
}

export async function getTicketByTrackingCode(
  trackingCode: string,
): Promise<CitizenTicketResponse> {
  const normalized = normalizeTrackingCode(trackingCode);
  if (!isValidTrackingCode(normalized)) {
    throw new Error(TRACK_LOOKUP_INVALID_MESSAGE);
  }

  if (config.useMockData) {
    return getTicketByTrackingCodeMock(normalized);
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(`/tickets/track/${encodeURIComponent(normalized)}`), {
      method: 'GET',
    });
  } catch (error) {
    if (isOfflineError(error)) {
      throw new Error(TRACK_LOOKUP_NETWORK_MESSAGE, { cause: error });
    }
    throw error;
  }

  if (response.status === 404) {
    throw new Error(TRACK_LOOKUP_NOT_FOUND_MESSAGE);
  }
  if (response.status === 400) {
    throw new Error(TRACK_LOOKUP_INVALID_MESSAGE);
  }
  if (!response.ok) {
    throw new Error(await parseApiError(response, TRACK_LOOKUP_NETWORK_MESSAGE));
  }

  return sanitizeCitizenTicket((await response.json()) as CitizenTicketResponse);
}

/** Local mock dataset for offline UI work — never used in staging/production. */
const MOCK_PUBLIC: PublicTicketResponse[] = [
  {
    ticketNumber: 'BG-100001',
    status: 'IN_PROGRESS',
    category: 'road_damage',
    description: 'Large pothole near campus gate slowing traffic.',
    location: { addressText: 'Near AUB Main Gate, Beirut' },
    mapLocation: {
      addressText: 'Near AUB Main Gate, Beirut',
      latitude: 33.9,
      longitude: 35.482,
    },
    department: { name: 'Roads' },
    attribution: { displayName: 'Community member', isNamed: false },
    photoUrl: null,
    createdAt: '2026-08-01T10:00:00Z',
    updatedAt: '2026-08-02T12:00:00Z',
  },
  {
    ticketNumber: 'BG-100002',
    status: 'SUBMITTED',
    category: 'street_lighting',
    description: 'Street light out on residential block.',
    location: { addressText: 'Hamra side street' },
    mapLocation: {
      addressText: 'Hamra side street',
      latitude: 33.897,
      longitude: 35.48,
    },
    department: null,
    attribution: { displayName: 'Ada Citizen', isNamed: true },
    photoUrl: null,
    createdAt: '2026-08-03T09:00:00Z',
    updatedAt: null,
  },
];

function getPublicTicketsMock({ limit = 20 }: { limit?: number }): PublicTicketListResponse {
  return {
    items: MOCK_PUBLIC.slice(0, limit).map(sanitizePublicTicket),
    nextCursor: null,
    limit,
  };
}

function getPublicTicketByNumberMock(ticketNumber: string): PublicTicketResponse {
  const found = MOCK_PUBLIC.find((item) => item.ticketNumber === ticketNumber);
  if (!found) {
    throw new Error(PUBLIC_TICKET_NOT_FOUND_MESSAGE);
  }
  return sanitizePublicTicket(found);
}

function getTicketByTrackingCodeMock(code: string): CitizenTicketResponse {
  if (code === 'ABC234') {
    return {
      ticketNumber: 'BG-100001',
      trackingCode: code,
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
    };
  }
  throw new Error(TRACK_LOOKUP_NOT_FOUND_MESSAGE);
}
