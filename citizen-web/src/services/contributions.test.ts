import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createTicket, getHistory, uploadPhoto, validateLocation } from '@/services/contributions';

describe('citizen contribution API', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('validates entered locations through the shared backend', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          location: { latitude: 33.9, longitude: 35.5, addressText: 'Beirut', source: 'MANUAL' },
        }),
        { status: 200 },
      ),
    );
    await expect(validateLocation({ addressText: 'Beirut' })).resolves.toMatchObject({
      addressText: 'Beirut',
    });
  });

  it('uploads the browser File with cookie credentials', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ imageObjectKey: 'reports/private/photo.jpg' }), {
        status: 200,
      }),
    );
    const file = new File(['photo'], 'issue.jpg', { type: 'image/jpeg' });
    await expect(uploadPhoto(file)).resolves.toBe('reports/private/photo.jpg');
    const init = fetchMock.mock.calls[0]?.[1];
    expect(init?.body).toBeInstanceOf(FormData);
    expect(init?.credentials).toBe('include');
  });

  it('uses the same idempotency key in the header and body and never sends an owner id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          ticketId: 't1',
          ticketNumber: 'BG-1',
          trackingCode: 'ABC234',
          status: 'SUBMITTED',
          message: 'ok',
          createdAt: 'now',
        }),
        { status: 201 },
      ),
    );
    await createTicket({
      description: 'Broken street light',
      location: { latitude: 33.9, longitude: 35.5, addressText: 'Beirut', source: 'MANUAL' },
      imageObjectKey: 'reports/private/photo.jpg',
      clientSubmissionId: 'submission-1',
    });
    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('submission-1');
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body.clientSubmissionId).toBe('submission-1');
    expect(body).not.toHaveProperty('ownerId');
    expect(body).not.toHaveProperty('userId');
  });

  it('loads paginated account-linked history', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify({ items: [], nextCursor: null, limit: 20 }), { status: 200 }),
      );
    await getHistory(20, 'next');
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      'http://localhost:8000/v1/citizen/me/tickets?limit=20&cursor=next',
    );
  });
});
