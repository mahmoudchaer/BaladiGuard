import type {
  CitizenTicketHistoryResponse,
  CitizenTicketResponse,
  PublicTicketListResponse,
  PublicTicketResponse,
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

const publicTickets: PublicTicketResponse[] = [
  {
    ticketNumber: 'BG-2026-0042',
    status: 'IN_PROGRESS',
    category: 'road_damage',
    description: 'Large pothole near the university gate causing traffic disruption.',
    location: { addressText: 'Hamra, Beirut' },
    mapLocation: {
      addressText: 'Hamra, Beirut',
      latitude: 33.896,
      longitude: 35.478,
    },
    department: { name: 'Road Maintenance' },
    attribution: { displayName: 'Community member', isNamed: false },
    photoUrl: 'https://images.unsplash.com/photo-1515165562839-978b710dce4a?w=640&q=80',
    createdAt: '2026-07-26T09:00:00Z',
    updatedAt: '2026-07-26T11:30:00Z',
  },
  {
    ticketNumber: 'BG-2026-0041',
    status: 'SUBMITTED',
    category: null,
    description: 'Street light is flickering beside the bus stop.',
    location: { addressText: 'Ras Beirut' },
    mapLocation: {
      addressText: 'Ras Beirut',
      latitude: 33.9,
      longitude: 35.482,
    },
    department: null,
    attribution: { displayName: 'Ada Citizen', isNamed: true },
    photoUrl: null,
    createdAt: '2026-07-25T13:15:00Z',
    updatedAt: '2026-07-25T13:15:00Z',
  },
];

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
    department: { name: 'Road Maintenance' },
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

export async function getPublicTicketsMock({
  limit = 20,
}: {
  limit?: number;
} = {}): Promise<PublicTicketListResponse> {
  await wait(350);

  return {
    items: publicTickets.slice(0, limit),
    nextCursor: null,
    limit,
  };
}

export async function getPublicTicketByNumberMock(
  ticketNumber: string,
): Promise<PublicTicketResponse> {
  await wait(250);
  const ticket = publicTickets.find((item) => item.ticketNumber === ticketNumber);
  if (!ticket) {
    throw new Error(
      'Unable to load public reports right now. Check your connection and try again.',
    );
  }
  return ticket;
}
