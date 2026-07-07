import { beforeEach, describe, expect, it, vi } from 'vitest';

import { submitReport } from '@/services/api/tickets';
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
}));

vi.mock('@/services/api/uploads', () => ({
  uploadReportPhoto: vi.fn(async () => 'reports/photos/uploaded.jpg'),
}));

import { submitTicketMock } from '@/services/api/mockTickets';
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
