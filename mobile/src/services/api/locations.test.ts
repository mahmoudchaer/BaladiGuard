import { afterEach, describe, expect, it, vi } from 'vitest';

const { appConfig } = vi.hoisted(() => ({
  appConfig: {
    apiBaseUrl: 'http://localhost:8000/v1',
    enableMockApi: false,
    appVersion: '0.1.0',
  },
}));

vi.mock('@/services/config', () => ({
  appConfig,
}));

afterEach(() => {
  appConfig.enableMockApi = false;
  appConfig.apiBaseUrl = 'http://localhost:8000/v1';
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('validateLocation', () => {
  it('calls the backend validation endpoint in real mode', async () => {
    appConfig.enableMockApi = false;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          location: {
            latitude: 33.896112,
            longitude: 35.478419,
            addressText: 'Near AUB Main Gate, Hamra, Beirut',
            source: 'MANUAL',
          },
          message: 'Location validated successfully.',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { validateLocation } = await import('@/services/api/locations');
    const result = await validateLocation({ addressText: 'AUB Main Gate' });

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/locations/validate', {
      method: 'POST',
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({ addressText: 'AUB Main Gate' }),
    });
    expect(result.success).toBe(true);
    expect(result.location?.latitude).toBe(33.896112);
  });

  it('uses local sample places in mock mode', async () => {
    appConfig.enableMockApi = true;

    const { validateLocation } = await import('@/services/api/locations');
    const result = await validateLocation({ addressText: 'Verdun Street' });

    expect(result.success).toBe(true);
    expect(result.location?.addressText).toContain('Verdun');
  });

  it('surfaces useful provider errors', async () => {
    appConfig.enableMockApi = false;

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'LOCATION_NOT_FOUND',
            message: 'We could not find that address.',
          },
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { validateLocation } = await import('@/services/api/locations');
    await expect(validateLocation({ addressText: 'unknown place' })).rejects.toThrow(
      'We could not find that address.',
    );
  });
});
