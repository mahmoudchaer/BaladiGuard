import { jsonRequest } from '@/services/api';
import type { CitizenProfile } from '@/types/citizen';
import type { CitizenRewards, PublicLeaderboard, RewardsPeriod } from '@/types/rewards';

export async function getMyRewards(): Promise<CitizenRewards> {
  return jsonRequest('/citizen/me/rewards', { method: 'GET' }, 'Unable to load rewards.');
}

export async function updateRewardsSettings(leaderboardOptIn: boolean): Promise<CitizenProfile> {
  return jsonRequest(
    '/citizen/me/rewards-settings',
    { method: 'PATCH', body: JSON.stringify({ leaderboardOptIn }) },
    'Unable to update leaderboard settings.',
  );
}

export async function getLeaderboard(
  period: RewardsPeriod,
  limit = 20,
  cursor?: string | null,
): Promise<PublicLeaderboard> {
  const params = new URLSearchParams({ period, limit: String(limit) });
  if (cursor) params.set('cursor', cursor);
  return jsonRequest(
    `/rewards/leaderboard?${params.toString()}`,
    { method: 'GET' },
    'Unable to load the leaderboard.',
  );
}
