import { appConfig } from '@/services/config';

type ApiErrorBody = {
  error?: {
    message?: string;
    code?: string;
  };
};

export function getClientHeaders(): Record<string, string> {
  return {
    'X-Client-Version': `mobile-${appConfig.appVersion}`,
  };
}

export async function parseApiError(
  response: Response,
  fallbackMessage: string,
): Promise<string> {
  const errorBody = (await response.json().catch(() => null)) as ApiErrorBody | null;
  return errorBody?.error?.message ?? fallbackMessage;
}
