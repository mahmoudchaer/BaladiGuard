import { useCallback, useEffect, useState } from 'react';
import { getLeaderboard } from '@/services/rewards';
import type { PublicLeaderboardEntry, RewardsPeriod } from '@/types/rewards';
import { useI18n } from '@/i18n/LocaleProvider';

export function LeaderboardPage() {
  const { t } = useI18n();
  const [period, setPeriod] = useState<RewardsPeriod>('all-time');
  const [items, setItems] = useState<PublicLeaderboardEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (next?: string | null, nextPeriod?: RewardsPeriod) => {
      setLoading(true);
      setError(null);
      try {
        const page = await getLeaderboard(nextPeriod ?? period, 20, next);
        setItems((current) => (next ? [...current, ...page.items] : page.items));
        setCursor(page.nextCursor);
      } catch (err) {
        setError(err instanceof Error ? err.message : t('leaderboard.loadFailed'));
      } finally {
        setLoading(false);
      }
    },
    [period, t],
  );

  useEffect(() => {
    void load(null, period);
  }, [load, period]);

  return (
    <section className="page page-enter narrow-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('leaderboard.eyebrow')}</span>
          <h1>{t('leaderboard.title')}</h1>
          <p className="lede">{t('leaderboard.lede')}</p>
        </div>
      </div>
      <div className="settings-card" role="group" aria-label={t('leaderboard.title')}>
        <button
          type="button"
          className={period === 'all-time' ? 'button' : 'text-button'}
          onClick={() => setPeriod('all-time')}
        >
          {t('leaderboard.allTime')}
        </button>
        <button
          type="button"
          className={period === 'monthly' ? 'button' : 'text-button'}
          onClick={() => setPeriod('monthly')}
        >
          {t('leaderboard.monthly')}
        </button>
      </div>
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      ) : null}
      {loading && !items.length ? <p>{t('common.loading')}</p> : null}
      {!loading && !items.length && !error ? (
        <div className="notice" role="status">
          <strong>{t('leaderboard.emptyTitle')}</strong>
          <p>{t('leaderboard.emptyBody')}</p>
        </div>
      ) : null}
      {items.length ? (
        <ol className="settings-card">
          {items.map((item) => (
            <li key={`${item.rank}-${item.displayName}-${item.points}`}>
              <strong>{t('leaderboard.rank', { rank: item.rank })}</strong> · {item.displayName} ·{' '}
              {t('leaderboard.points', { points: item.points })} · {item.levelTitle}
            </li>
          ))}
        </ol>
      ) : null}
      {cursor ? (
        <button
          className="button"
          type="button"
          disabled={loading}
          onClick={() => void load(cursor)}
        >
          {t('leaderboard.loadMore')}
        </button>
      ) : null}
      <p className="helper">{t('leaderboard.tieNote')}</p>
    </section>
  );
}
