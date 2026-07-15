import { vi } from 'vitest';

export function mockFetchJson(body: unknown, init: ResponseInit = {}) {
  const response = {
    ok: init.status ? init.status >= 200 && init.status < 300 : true,
    status: init.status ?? 200,
    json: async () => body,
  } as Response;

  vi.stubGlobal(
    'fetch',
    vi.fn(async () => response),
  );
}
