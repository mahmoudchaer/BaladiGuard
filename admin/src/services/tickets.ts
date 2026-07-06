import type { Ticket } from '@/types/ticket';
import mockTickets from '../../../mock_tickets.json';
import { config } from '@/services/config';

const MOCK_LOAD_DELAY_MS = 350;

function isTicketArray(value: unknown): value is Ticket[] {
  return Array.isArray(value);
}

async function fetchMockTickets(): Promise<Ticket[]> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LOAD_DELAY_MS));

  if (!isTicketArray(mockTickets)) {
    throw new Error('Invalid mock ticket fixtures.');
  }

  return [...mockTickets].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
}

async function fetchTicketsFromApi(): Promise<Ticket[]> {
  const response = await fetch(`${config.apiBaseUrl}/v1/tickets`);

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const message = errorBody?.error?.message ?? 'Unable to load tickets from the server.';
    throw new Error(message);
  }

  const data: unknown = await response.json();

  if (!isTicketArray(data)) {
    throw new Error('Unexpected ticket list response shape.');
  }

  return data;
}

export async function fetchTickets(): Promise<Ticket[]> {
  if (config.useMockData) {
    return fetchMockTickets();
  }

  return fetchTicketsFromApi();
}
