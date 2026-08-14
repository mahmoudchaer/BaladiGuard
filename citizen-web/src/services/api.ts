import { config } from '@/services/config';

type ApiErrorBody = { error?: { code?: string; message?: string } };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = 'UNKNOWN',
    readonly retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function apiUrl(path: string): string {
  return `${config.apiBaseUrl}/v1${path}`;
}

let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      credentials: 'include',
      headers: { 'X-Client-Version': 'citizen-web-0.1.0', ...init.headers },
    });
    if (response.status === 401) unauthorizedHandler?.();
    return response;
  } catch {
    throw new ApiError(
      'You appear to be offline. Check your connection and try again.',
      0,
      'OFFLINE',
    );
  }
}

export async function apiError(response: Response, fallback: string): Promise<ApiError> {
  const body = (await response
    .clone()
    .json()
    .catch(() => null)) as ApiErrorBody | null;
  const retryRaw = response.headers.get('Retry-After');
  const retry = retryRaw ? Number.parseInt(retryRaw, 10) : NaN;
  return new ApiError(
    body?.error?.message || fallback,
    response.status,
    body?.error?.code || (response.status === 429 ? 'RATE_LIMITED' : 'UNKNOWN'),
    Number.isFinite(retry) ? retry : null,
  );
}

export async function jsonRequest<T>(
  path: string,
  init: RequestInit,
  fallback: string,
): Promise<T> {
  const response = await apiFetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) throw await apiError(response, fallback);
  return response.json() as Promise<T>;
}
