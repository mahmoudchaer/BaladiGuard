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
});
