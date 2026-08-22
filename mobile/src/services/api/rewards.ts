import { appConfig } from '@/services/config';
import { CitizenAuthApiError } from '@/services/api/citizenAuth';
import { getAuthHeaders, parseApiError } from '@/services/api/http';

export type RewardsPeriod = 'all-time' | 'monthly';

export type CitizenRewards = {
  confirmedPoints: number;
  pendingPoints: number;
  monthlyPoints: number;
  levelTitle: string;
  privateRankAllTime: number | null;
  participation: {
    optedIn: boolean;
    eligible: boolean;
    missing: string[];
  };
  badges: string[];
  recognitionOnly: boolean;
};

export type PublicLeaderboard = {
  period: RewardsPeriod;
  items: Array<{ rank: number; displayName: string; points: number; levelTitle: string }>;
  nextCursor: string | null;
};

async function rewardsFetch(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${appConfig.apiBaseUrl}/v1${path}`, {
      ...init,
      headers: {
        ...getAuthHeaders(),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new CitizenAuthApiError(
      'Unable to reach the server. Check your connection and try again.',
      { code: 'NETWORK_ERROR', status: 0 },
    );
  }
}

export async function getMyRewards(): Promise<CitizenRewards> {
  const response = await rewardsFetch('/citizen/me/rewards', { method: 'GET' });
  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to load rewards.');
    throw new CitizenAuthApiError(message, { code: 'UNKNOWN', status: response.status });
  }
  return response.json() as Promise<CitizenRewards>;
}

export async function getLeaderboard(
  period: RewardsPeriod,
  cursor?: string | null,
): Promise<PublicLeaderboard> {
  const params = new URLSearchParams({ period, limit: '20' });
  if (cursor) params.set('cursor', cursor);
  const response = await rewardsFetch(`/rewards/leaderboard?${params.toString()}`, {
    method: 'GET',
  });
  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to load the leaderboard.');
    throw new CitizenAuthApiError(message, { code: 'UNKNOWN', status: response.status });
  }
  return response.json() as Promise<PublicLeaderboard>;
}
