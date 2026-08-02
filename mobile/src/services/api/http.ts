import { appConfig } from '@/services/config';

type ApiErrorBody = {
  error?: {
    message?: string;
    code?: string;
  };
};

let accessTokenProvider: (() => string | null) | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setCitizenAccessTokenProvider(provider: (() => string | null) | null): void {
  accessTokenProvider = provider;
}

export function setCitizenUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function notifyCitizenUnauthorized(): void {
  unauthorizedHandler?.();
}

export function getClientHeaders(): Record<string, string> {
  return {
    'X-Client-Version': `mobile-${appConfig.appVersion}`,
  };
}

/** Client headers plus optional Bearer token for authenticated citizen calls. */
export function getAuthHeaders(accessToken?: string | null): Record<string, string> {
  const headers = getClientHeaders();
  const token = accessToken ?? accessTokenProvider?.() ?? null;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function parseApiError(response: Response, fallbackMessage: string): Promise<string> {
  const errorBody = (await response.json().catch(() => null)) as ApiErrorBody | null;
  return errorBody?.error?.message ?? fallbackMessage;
}

export async function parseApiErrorCode(response: Response): Promise<string | null> {
  const errorBody = (await response.json().catch(() => null)) as ApiErrorBody | null;
  return errorBody?.error?.code ?? null;
}

export function handleUnauthorizedResponse(status: number): void {
  if (status === 401) {
    notifyCitizenUnauthorized();
  }
}
