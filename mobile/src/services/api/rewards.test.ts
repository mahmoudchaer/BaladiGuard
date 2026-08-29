import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getLeaderboard, getMyRewards } from '@/services/api/rewards';

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

vi.mock('@/services/api/http', () => ({
  getAuthHeaders: () => ({ Authorization: 'Bearer tok' }),
  parseApiError: async () => 'Unable to load rewards.',
}));

const rewards = {
  confirmedPoints: 12,
  pendingPoints: 3,
  monthlyPoints: 4,
  levelTitle: 'Neighbor',
  nextLevelTitle: 'Guardian',
  pointsToNextLevel: 8,
  privateRankAllTime: 2,
  publicRankAllTime: null,
  participation: { optedIn: false, eligible: false, missing: ['fullName'] },
  badges: [],
  recentEvents: [],
  recognitionOnly: true,
};

describe('citizen rewards API', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('calls /v1 once for my rewards', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => rewards,
    } as Response);

    await expect(getMyRewards()).resolves.toEqual(rewards);
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/me/rewards',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('calls /v1 once for the public leaderboard', async () => {
    const page = { period: 'all-time', items: [], nextCursor: null };
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => page,
    } as Response);

    await expect(getLeaderboard('all-time')).resolves.toEqual(page);
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/rewards/leaderboard?period=all-time&limit=20',
      expect.objectContaining({ method: 'GET' }),
    );
  });
});
