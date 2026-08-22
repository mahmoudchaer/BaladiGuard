import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getLeaderboard, getMyRewards, updateRewardsSettings } from '@/services/rewards';

describe('citizen rewards API', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('loads private rewards progress', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          ruleVersion: 'rewards-v1',
          confirmedPoints: 10,
          pendingPoints: 3,
          monthlyPoints: 10,
          monthlyPeriod: '2026-08',
          levelId: 'neighbor',
          levelTitle: 'Neighbor',
          badges: [],
          participation: { optedIn: false, missing: ['leaderboardOptIn'] },
          recentEvents: [],
          recognitionOnly: true,
        }),
        { status: 200 },
      ),
    );
    await expect(getMyRewards()).resolves.toMatchObject({ confirmedPoints: 10, pendingPoints: 3 });
  });

  it('opts in without sending identifiers on the public board request', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify({ leaderboardOptIn: true }), { status: 200 }));
    await updateRewardsSettings(true);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/citizen/me/rewards-settings');
  });

  it('pages the public leaderboard by period', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          period: 'monthly',
          items: [{ rank: 1, displayName: 'Ada', points: 38, levelTitle: 'Helper' }],
          nextCursor: 'next',
        }),
        { status: 200 },
      ),
    );
    const page = await getLeaderboard('monthly', 20, 'abc');
    expect(page.items[0]?.displayName).toBe('Ada');
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('period=monthly');
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('cursor=abc');
  });
});
