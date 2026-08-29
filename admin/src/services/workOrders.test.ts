import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/config', () => ({
  config: { apiBaseUrl: 'http://localhost:8000', useMockData: false },
}));

vi.mock('@/services/auth', () => ({
  getStaffAuthHeaders: () => ({ Authorization: 'Bearer test-token' }),
}));

describe('workOrders service', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('creates a work order through the staff API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          workOrderId: 'wo_1',
          ticketId: 'tkt_123',
          municipalityId: 'muni',
          departmentId: 'dept',
          state: 'QUEUED',
          summary: 'Fix the road',
          createdAt: '2026-08-15T10:00:00Z',
          createdBy: 'staff_admin_001',
          updatedAt: '2026-08-15T10:00:00Z',
          updatedBy: 'staff_admin_001',
          created: true,
        }),
        { status: 201, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { createTicketWorkOrder } = await import('@/services/workOrders');
    const created = await createTicketWorkOrder('tkt_123', { summary: 'Fix the road' });

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/tickets/tkt_123/work-orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token',
      },
      body: JSON.stringify({ summary: 'Fix the road' }),
    });
    expect(created.workOrderId).toBe('wo_1');
    expect(created.created).toBe(true);
  });

  it('uploads before/after evidence without letting the client choose the object key', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          evidenceId: 'ev_1',
          ticketId: 'tkt_123',
          workOrderId: 'wo_1',
          kind: 'AFTER',
          objectKey: 'work-orders/evidence/v1/scope/wo_1/after/abc.png',
          contentType: 'image/png',
          uploadedBy: 'staff_admin_001',
          createdAt: '2026-08-15T10:00:00Z',
          source: 'UPLOAD',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { uploadWorkOrderEvidence } = await import('@/services/workOrders');
    const file = new File(['img'], 'after.png', { type: 'image/png' });
    const evidence = await uploadWorkOrderEvidence('wo_1', 'AFTER', file);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/work-orders/wo_1/evidence?kind=AFTER',
      expect.objectContaining({ method: 'POST' }),
    );
    const body = fetchMock.mock.calls[0][1].body as FormData;
    expect(body.get('file')).toBe(file);
    expect(evidence.objectKey).toContain('work-orders/evidence/v1/');
  });
});
