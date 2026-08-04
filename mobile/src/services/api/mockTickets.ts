import type {
  CitizenTicketHistoryResponse,
  CitizenTicketResponse,
  SubmitTicketRequest,
  SubmitTicketResponse,
} from '@/types/ticket';
import {
  TRACKING_CODE_ALPHABET,
  TRACKING_CODE_LENGTH,
  normalizeTrackingCode,
} from '@/utils/trackingCode';

const MOCK_TICKET_PREFIXES = ['RD', 'SL', 'WS', 'WD', 'SW'];

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const createMockTicketNumber = () => {
  const prefix = MOCK_TICKET_PREFIXES[Math.floor(Math.random() * MOCK_TICKET_PREFIXES.length)];
  const year = new Date().getFullYear();
  const sequence = String(Math.floor(Math.random() * 9000) + 1000).padStart(4, '0');
  return `${prefix}-${year}-${sequence}`;
};

const createTrackingCode = () =>
  Array.from({ length: TRACKING_CODE_LENGTH }, () => {
    const index = Math.floor(Math.random() * TRACKING_CODE_ALPHABET.length);
    return TRACKING_CODE_ALPHABET[index];
  }).join('');

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

/** Deterministic mock lookup for local demos when EXPO_PUBLIC_ENABLE_MOCK_API=true. */
export async function getTicketByTrackingCodeMock(
  trackingCode: string,
): Promise<CitizenTicketResponse> {
  await wait(350);
  const normalized = normalizeTrackingCode(trackingCode);
  const createdAt = '2026-07-26T09:00:00Z';
  const updatedAt = '2026-07-26T11:30:00Z';

  return {
    ticketNumber: 'BG-2026-0042',
    trackingCode: normalized,
    status: 'IN_PROGRESS',
    category: 'road_damage',
    location: { addressText: 'Near AUB Main Gate, Hamra, Beirut' },
    createdAt,
    updatedAt,
    lastUpdatedAt: updatedAt,
    timeline: [
      { status: 'SUBMITTED', changedAt: createdAt },
      { status: 'UNDER_REVIEW', changedAt: '2026-07-26T10:00:00Z' },
      { status: 'IN_PROGRESS', changedAt: updatedAt },
    ],
  };
}

export async function getCitizenTicketHistoryMock(): Promise<CitizenTicketHistoryResponse> {
  await wait(350);

  return {
    items: [
      {
        trackingCode: 'AB23CD',
        status: 'IN_PROGRESS',
        category: 'road_damage',
        locationAddress: 'Near AUB Main Gate, Hamra, Beirut',
        submittedAt: '2026-07-26T09:00:00Z',
      },
      {
        trackingCode: 'CD45EF',
        status: 'SUBMITTED',
        category: null,
        locationAddress: 'Bliss Street, Beirut',
        submittedAt: '2026-07-25T13:15:00Z',
      },
    ],
    nextCursor: null,
    limit: 20,
  };
}
