import { describe, expect, it } from 'vitest';
import type { Ticket } from '@/types/ticket';
import {
  getPlottableTickets,
  isPlottableLocation,
  isPlottableTicket,
  buildGoogleMapsUrl,
} from '@/utils/ticketLocation';

function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    ticketId: 'tkt_1',
    ticketNumber: 'BG-2026-0001',
    trackingCode: 'ABC123',
    description: 'Test ticket',
    contact: {},
    location: {
      latitude: 33.896,
      longitude: 35.478,
      addressText: 'Hamra, Beirut',
      source: 'GPS',
    },
    imageObjectKey: 'reports/tkt_1.jpg',
    status: 'SUBMITTED',
    category: 'road_damage',
    priority: null,
    createdBy: null,
    municipalityId: null,
    departmentId: null,
    duplicateGroupId: null,
    createdAt: '2026-07-17T08:00:00Z',
    updatedAt: '2026-07-17T08:01:00Z',
    ...overrides,
  };
}

describe('isPlottableLocation', () => {
  it('accepts valid finite coordinates', () => {
    expect(
      isPlottableLocation({
        latitude: 33.89,
        longitude: 35.5,
        addressText: 'Beirut',
        source: 'GPS',
      }),
    ).toBe(true);
  });

  it('rejects missing, non-finite, and out-of-range coordinates', () => {
    expect(isPlottableLocation(null)).toBe(false);
    expect(isPlottableLocation(undefined)).toBe(false);
    expect(isPlottableLocation({ latitude: NaN, longitude: 35 })).toBe(false);
    expect(isPlottableLocation({ latitude: 33, longitude: Infinity })).toBe(false);
    expect(isPlottableLocation({ latitude: 91, longitude: 35 })).toBe(false);
    expect(isPlottableLocation({ latitude: 33, longitude: -181 })).toBe(false);
  });
});

describe('getPlottableTickets', () => {
  it('keeps only tickets with plottable locations', () => {
    const valid = makeTicket({ ticketId: 'valid' });
    const invalid = makeTicket({
      ticketId: 'invalid',
      location: {
        latitude: Number.NaN,
        longitude: 35.5,
        addressText: 'Unknown',
        source: 'PLACEHOLDER',
      },
    });

    expect(isPlottableTicket(valid)).toBe(true);
    expect(isPlottableTicket(invalid)).toBe(false);
    expect(getPlottableTickets([valid, invalid])).toEqual([valid]);
  });
});

describe('buildGoogleMapsUrl', () => {
  it('builds a Google Maps query URL from coordinates', () => {
    expect(buildGoogleMapsUrl(33.896112, 35.478419)).toBe(
      'https://www.google.com/maps?q=33.896112,35.478419',
    );
  });
});
