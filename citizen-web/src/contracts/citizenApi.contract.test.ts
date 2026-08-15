import { describe, expect, it } from 'vitest';
import { sanitizeCitizenTicket, sanitizePublicTicket } from '@/services/tickets';
import type { CitizenTicketResponse, PublicTicketResponse } from '@/types/ticket';
import {
  FORBIDDEN_PUBLIC_KEYS,
  FORBIDDEN_TRACK_KEYS,
  historyFixture,
  profileFixture,
  publicListFixture,
  publicMapFixture,
  publicTicketFixture,
  leakedResolvedTrackPayload,
  resolvedTrackFixture,
  submitFixture,
  trackFixture,
} from '@/contracts/fixtures';

function assertNoKeys(value: object, keys: readonly string[]) {
  const record = value as Record<string, unknown>;
  for (const key of keys) {
    expect(record).not.toHaveProperty(key);
  }
}

function assertSafePhotoUrl(url: string | null | undefined) {
  if (url == null || url === '') {
    return;
  }
  expect(url).toMatch(/^https:\/\//);
  expect(url).not.toMatch(/imageObjectKey|reports\/photos|reports\/private/);
}

describe('citizen API contracts', () => {
  it('requires the public ticket projection and rejects staff-only keys', () => {
    expect(publicTicketFixture.ticketNumber).toMatch(/^BG-/);
    expect(publicTicketFixture.mapLocation.latitude).toEqual(expect.any(Number));
    expect(publicTicketFixture.attribution.displayName).toBeTruthy();
    assertSafePhotoUrl(publicTicketFixture.photoUrl);
    assertNoKeys(publicTicketFixture, FORBIDDEN_PUBLIC_KEYS);

    const leaked = {
      ...publicTicketFixture,
      ticketId: 'secret',
      trackingCode: 'ABC234',
      imageObjectKey: 'reports/photos/original.jpg',
    } as PublicTicketResponse & Record<string, unknown>;
    const clean = sanitizePublicTicket(leaked);
    assertNoKeys(clean, FORBIDDEN_PUBLIC_KEYS);
    assertSafePhotoUrl(clean.photoUrl);
  });

  it('requires public list and map viewport shapes used by browse/clustering', () => {
    expect(publicListFixture.items).toHaveLength(1);
    expect(publicListFixture).toHaveProperty('nextCursor');
    expect(publicListFixture.limit).toBeGreaterThan(0);

    expect(publicMapFixture.markers[0]).toMatchObject({
      ticketNumber: expect.any(String),
      latitude: expect.any(Number),
      longitude: expect.any(Number),
    });
    assertNoKeys(publicMapFixture.markers[0] ?? {}, [
      'photoUrl',
      'imageObjectKey',
      'ticketId',
      'trackingCode',
    ]);
    expect(publicMapFixture.clusters[0]).toMatchObject({
      id: expect.any(String),
      count: expect.any(Number),
    });
  });

  it('requires possession tracking fields and strips staff-only leaks', () => {
    expect(trackFixture.trackingCode).toHaveLength(6);
    expect(trackFixture.timeline[0]?.status).toBe('SUBMITTED');
    assertNoKeys(trackFixture, FORBIDDEN_TRACK_KEYS);

    const leaked = {
      ...trackFixture,
      ticketId: 'secret',
      imageObjectKey: 'reports/photos/original.jpg',
      contact: { phone: '+961' },
    } as CitizenTicketResponse & Record<string, unknown>;
    const clean = sanitizeCitizenTicket(leaked);
    assertNoKeys(clean, FORBIDDEN_TRACK_KEYS);
    expect(clean.trackingCode).toBe('ABC234');
    expect(clean.outcomeMessage).toBeNull();
  });

  it('keeps the citizen-safe outcome message and drops private resolution fields', () => {
    expect(resolvedTrackFixture.status).toBe('RESOLVED');
    expect(resolvedTrackFixture.outcomeMessage).toBe('The reported issue has been resolved.');
    assertNoKeys(resolvedTrackFixture, FORBIDDEN_TRACK_KEYS);

    const clean = sanitizeCitizenTicket(
      leakedResolvedTrackPayload as CitizenTicketResponse & Record<string, unknown>,
    );
    expect(clean.outcomeMessage).toBe('The reported issue has been resolved.');
    expect(clean.status).toBe('RESOLVED');
    assertNoKeys(clean, FORBIDDEN_TRACK_KEYS);
    expect(JSON.stringify(clean)).not.toMatch(
      /WORK_COMPLETED|private crew address|Internal close note|do not show|secret-ticket-id/,
    );
  });

  it('requires history, profile, and submit envelopes without copying backend rules', () => {
    expect(historyFixture.items[0]?.trackingCode).toBeTruthy();
    assertNoKeys(historyFixture.items[0] ?? {}, ['ticketId', 'imageObjectKey', 'ownerUserId']);

    expect(profileFixture.contributionReady).toBe(true);
    expect(profileFixture).not.toHaveProperty('otp');
    expect(profileFixture).not.toHaveProperty('sessionToken');
    expect(profileFixture).not.toHaveProperty('accessToken');

    expect(submitFixture.ticketNumber).toBeTruthy();
    expect(submitFixture.trackingCode).toBeTruthy();
    expect(submitFixture.status).toBe('SUBMITTED');
  });
});
