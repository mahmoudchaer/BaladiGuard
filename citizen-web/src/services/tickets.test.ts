import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  TRACK_LOOKUP_INVALID_MESSAGE,
  TRACK_LOOKUP_NOT_FOUND_MESSAGE,
  getPublicTicketByNumber,
  getPublicMapViewport,
  getPublicTickets,
  getTicketByTrackingCode,
  sanitizePublicTicket,
} from '@/services/tickets';
import type { PublicTicketResponse } from '@/types/ticket';

vi.mock('@/services/config', () => ({
  config: {
    appEnv: 'local',
    apiBaseUrl: 'http://localhost:8000',
    useMockData: false,
  },
}));

describe('sanitizePublicTicket', () => {
  it('keeps only citizen-safe public fields', () => {
    const dirty = {
      ticketNumber: 'BG-1',
      status: 'SUBMITTED',
      category: 'road_damage',
      description: 'Pothole',
      location: { addressText: 'Hamra' },
      mapLocation: { addressText: 'Hamra', latitude: 33.9, longitude: 35.5 },
      department: { name: 'Roads' },
      attribution: { displayName: 'Community member', isNamed: false },
      photoUrl: 'https://cdn.example/public.jpg',
      createdAt: '2026-08-01T00:00:00Z',
      updatedAt: null,
      ticketId: 'secret-id',
      trackingCode: 'ABC234',
      contact: { email: 'x@y.com' },
      imageObjectKey: 'private/key.jpg',
    } as PublicTicketResponse & Record<string, unknown>;

    const clean = sanitizePublicTicket(dirty);
    expect(clean).toEqual({
      ticketNumber: 'BG-1',
      status: 'SUBMITTED',
      category: 'road_damage',
      description: 'Pothole',
      location: { addressText: 'Hamra' },
      mapLocation: { addressText: 'Hamra', latitude: 33.9, longitude: 35.5 },
      department: { name: 'Roads' },
      attribution: { displayName: 'Community member', isNamed: false },
      photoUrl: 'https://cdn.example/public.jpg',
      createdAt: '2026-08-01T00:00:00Z',
      updatedAt: null,
    });
    expect(clean).not.toHaveProperty('ticketId');
    expect(clean).not.toHaveProperty('trackingCode');
    expect(clean).not.toHaveProperty('contact');
    expect(clean).not.toHaveProperty('imageObjectKey');
  });
});

describe('tickets API', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it('lists public tickets with pagination cursor', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            ticketNumber: 'BG-1',
            status: 'SUBMITTED',
            category: null,
            description: 'x',
            location: { addressText: 'A' },
            mapLocation: { addressText: 'A', latitude: 1, longitude: 2 },
            attribution: { displayName: 'Community member', isNamed: false },
            photoUrl: null,
            createdAt: '2026-08-01T00:00:00Z',
            updatedAt: null,
          },
        ],
        nextCursor: 'cursor-2',
        limit: 20,
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const page = await getPublicTickets({ limit: 20, cursor: 'cursor-1' });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/tickets/public?limit=20&cursor=cursor-1',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(page.nextCursor).toBe('cursor-2');
    expect(page.items[0]?.ticketNumber).toBe('BG-1');
  });

  it('loads public detail by ticket number', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ticketNumber: 'BG-9',
        status: 'IN_PROGRESS',
        category: 'road_damage',
        description: 'Hole',
        location: { addressText: 'A' },
        mapLocation: { addressText: 'A', latitude: 1, longitude: 2 },
        attribution: { displayName: 'Ada', isNamed: true },
        photoUrl: null,
        createdAt: '2026-08-01T00:00:00Z',
        updatedAt: null,
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const detail = await getPublicTicketByNumber('bg-9');
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/tickets/public/BG-9',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(detail.ticketNumber).toBe('BG-9');
  });

  it('loads only the requested public map viewport', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        markers: [
          {
            ticketNumber: 'BG-9',
            status: 'SUBMITTED',
            category: 'road_damage',
            addressText: 'Hamra',
            latitude: 33.9,
            longitude: 35.5,
          },
        ],
        clusters: [],
        limit: 200,
        truncated: false,
        zoom: 15,
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await getPublicMapViewport({
      north: 34,
      south: 33,
      east: 36,
      west: 35,
      zoom: 15,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/v1/tickets/public/map?'),
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result.markers[0]?.ticketNumber).toBe('BG-9');
    expect(result.truncated).toBe(false);
  });

  it('uses fixed tracking validation and not-found copy', async () => {
    await expect(getTicketByTrackingCode('bad')).rejects.toThrow(TRACK_LOOKUP_INVALID_MESSAGE);

    const fetchMock = vi.fn().mockResolvedValue({ status: 404, ok: false });
    vi.stubGlobal('fetch', fetchMock);
    await expect(getTicketByTrackingCode('ABC234')).rejects.toThrow(TRACK_LOOKUP_NOT_FOUND_MESSAGE);
  });
});
