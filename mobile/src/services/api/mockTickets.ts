import type { SubmitTicketRequest, SubmitTicketResponse } from '@/types/ticket';

const MOCK_TICKET_PREFIXES = ['RD', 'SL', 'WS', 'WD', 'SW'];

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const createMockTicketNumber = () => {
  const prefix = MOCK_TICKET_PREFIXES[Math.floor(Math.random() * MOCK_TICKET_PREFIXES.length)];
  const year = new Date().getFullYear();
  const sequence = String(Math.floor(Math.random() * 9000) + 1000).padStart(4, '0');
  return `${prefix}-${year}-${sequence}`;
};

const createTrackingCode = () => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({ length: 6 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
};

export async function submitTicketMock(
  payload: SubmitTicketRequest,
): Promise<SubmitTicketResponse> {
  await wait(900);

  const ticketNumber = createMockTicketNumber();

  return {
    ticketId: `tkt_mock_${Date.now()}`,
    ticketNumber,
    trackingCode: createTrackingCode(),
    status: 'SUBMITTED',
    message: 'Your report was submitted successfully.',
    createdAt: new Date().toISOString(),
  };
}
