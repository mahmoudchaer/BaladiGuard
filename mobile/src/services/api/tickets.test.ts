import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  TICKET_HISTORY_NETWORK_MESSAGE,
  TICKET_HISTORY_UNAUTHORIZED_MESSAGE,
  TRACK_LOOKUP_INVALID_MESSAGE,
  TRACK_LOOKUP_NOT_FOUND_MESSAGE,
  getCitizenTicketHistory,
  getTicketByTrackingCode,
  submitReport,
} from '@/services/api/tickets';
import type { ReportFormValues } from '@/schemas/reportFormSchema';

const formValues: ReportFormValues = {
  description: 'Large pothole near the university gate causing traffic disruption.',
  contactName: 'Citizen Name',
  phone: '+96170123456',
  email: 'citizen@example.com',
  addressText: 'Near AUB Main Gate, Hamra, Beirut',
  latitude: 33.896112,
  longitude: 35.478419,
  locationSource: 'PLACEHOLDER',
  photoUri: 'file:///photo.jpg',
  photoFileName: 'photo.jpg',
  photoContentType: 'image/jpeg',
};

const mockTicketResponse = {
  ticketId: 'tkt_test',
  ticketNumber: 'BG-2026-0001',
  trackingCode: 'AB12CD',
  status: 'SUBMITTED' as const,
  message: 'Your report was submitted successfully.',
  createdAt: '2026-07-07T00:00:00Z',
};

const mockCitizenTicket = {
  ticketNumber: 'BG-2026-0001',
  trackingCode: 'AB23CD',
  status: 'IN_PROGRESS' as const,
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Hamra, Beirut' },
  createdAt: '2026-07-07T00:00:00Z',
  updatedAt: '2026-07-07T02:00:00Z',
  lastUpdatedAt: '2026-07-07T02:00:00Z',
  timeline: [{ status: 'SUBMITTED' as const, changedAt: '2026-07-07T00:00:00Z' }],
};

const mockCitizenHistory = {
  items: [
    {
      trackingCode: 'AB23CD',
      status: 'IN_PROGRESS' as const,
      category: 'road_damage',
      locationAddress: 'Near AUB Main Gate, Hamra, Beirut',
      submittedAt: '2026-07-07T00:00:00Z',
    },
  ],
  nextCursor: null,
  limit: 20,
};

const { appConfig } = vi.hoisted(() => ({
  appConfig: {
    apiBaseUrl: 'http://localhost:8000/v1',
    enableMockApi: false,
    appVersion: '0.1.0',
  },
}));

vi.mock('react-native', () => ({
  Platform: { OS: 'ios' },
}));

vi.mock('@/services/config', () => ({
  appConfig,
}));

vi.mock('@/services/api/mockTickets', () => ({
  submitTicketMock: vi.fn(async () => mockTicketResponse),
  getTicketByTrackingCodeMock: vi.fn(async () => mockCitizenTicket),
  getCitizenTicketHistoryMock: vi.fn(async () => mockCitizenHistory),
}));

vi.mock('@/services/api/uploads', () => ({
  uploadReportPhoto: vi.fn(async () => 'reports/photos/uploaded.jpg'),
}));

import {
  getCitizenTicketHistoryMock,
  getTicketByTrackingCodeMock,
  submitTicketMock,
} from '@/services/api/mockTickets';
import { uploadReportPhoto } from '@/services/api/uploads';

describe('submitReport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appConfig.enableMockApi = false;
    vi.stubGlobal('fetch', vi.fn());
  });

  it('uses the mock path when mock mode is enabled', async () => {
    appConfig.enableMockApi = true;

    const response = await submitReport(formValues);

    expect(response).toEqual(mockTicketResponse);
    expect(submitTicketMock).toHaveBeenCalledOnce();
    expect(uploadReportPhoto).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('uploads the photo before submitting the ticket in the real API path', async () => {
    const progress: string[] = [];
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockTicketResponse,
    } as Response);

    const response = await submitReport(formValues, {
      onProgress: (phase) => progress.push(phase),
    });

    expect(uploadReportPhoto).toHaveBeenCalledOnce();
    expect(progress).toEqual(['uploading-photo', 'submitting-report']);
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/tickets',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"imageObjectKey":"reports/photos/uploaded.jpg"'),
      }),
    );
    expect(response).toEqual(mockTicketResponse);
  });

  it('does not submit a ticket when photo upload fails', async () => {
    vi.mocked(uploadReportPhoto).mockRejectedValueOnce(new Error('Upload failed'));

    await expect(submitReport(formValues)).rejects.toThrow('Upload failed');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('surfaces a clear error when ticket submission fails after upload', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      json: async () => ({ error: { message: 'Validation failed.' } }),
    } as Response);

    await expect(submitReport(formValues)).rejects.toThrow(
      'Your photo was uploaded, but the report could not be saved. Validation failed.',
    );
  });
});

describe('getTicketByTrackingCode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appConfig.enableMockApi = false;
    vi.stubGlobal('fetch', vi.fn());
  });

  it('rejects invalid codes without calling the API', async () => {
    await expect(getTicketByTrackingCode('AB1OCD')).rejects.toThrow(TRACK_LOOKUP_INVALID_MESSAGE);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('calls the approved public track endpoint with a normalized code', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockCitizenTicket,
    } as Response);

    const result = await getTicketByTrackingCode('  ab23cd  ');

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/tickets/track/AB23CD',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result).toEqual(mockCitizenTicket);
  });

  it('maps not-found to a fixed non-sensitive message', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        error: { code: 'TICKET_NOT_FOUND', message: 'Ticket was not found.' },
      }),
    } as Response);

    await expect(getTicketByTrackingCode('AB23CD')).rejects.toThrow(TRACK_LOOKUP_NOT_FOUND_MESSAGE);
  });

  it('uses the mock lookup path when mock mode is enabled', async () => {
    appConfig.enableMockApi = true;

    const result = await getTicketByTrackingCode('AB23CD');

    expect(getTicketByTrackingCodeMock).toHaveBeenCalledWith('AB23CD');
    expect(result).toEqual(mockCitizenTicket);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('getCitizenTicketHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appConfig.enableMockApi = false;
    vi.stubGlobal('fetch', vi.fn());
  });

  it('calls the protected citizen history endpoint with auth and pagination params', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockCitizenHistory,
    } as Response);

    const result = await getCitizenTicketHistory({
      accessToken: 'citizen-token',
      limit: 10,
      cursor: '20',
    });

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/me/tickets?limit=10&cursor=20',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer citizen-token' }),
      }),
    );
    expect(result).toEqual(mockCitizenHistory);
  });

  it('maps unauthorized history responses to a session-expired message', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { code: 'UNAUTHORIZED' } }),
    } as Response);

    await expect(getCitizenTicketHistory({ accessToken: 'expired-token' })).rejects.toThrow(
      TICKET_HISTORY_UNAUTHORIZED_MESSAGE,
    );
  });

  it('maps offline failures to a retryable history message', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Network request failed'));

    await expect(getCitizenTicketHistory({ accessToken: 'token' })).rejects.toThrow(
      TICKET_HISTORY_NETWORK_MESSAGE,
    );
  });

  it('uses the mock history path when mock mode is enabled', async () => {
    appConfig.enableMockApi = true;

    const result = await getCitizenTicketHistory({ accessToken: 'token' });

    expect(getCitizenTicketHistoryMock).toHaveBeenCalledOnce();
    expect(result).toEqual(mockCitizenHistory);
    expect(fetch).not.toHaveBeenCalled();
  });
});
