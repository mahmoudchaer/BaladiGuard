import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMyRewards } from '@/services/rewards';
import type { CitizenRewards } from '@/types/rewards';
import { useI18n } from '@/i18n/LocaleProvider';

export function RewardsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<CitizenRewards | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getMyRewards()
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t('rewards.loadFailed'));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <section className="page page-enter narrow-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('rewards.eyebrow')}</span>
          <h1>{t('rewards.title')}</h1>
          <p className="lede">{t('rewards.lede')}</p>
        </div>
        <Link className="button" to="/leaderboard">
          {t('rewards.openLeaderboard')}
        </Link>
      </div>
      {loading ? <p>{t('common.loading')}</p> : null}
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      ) : null}
      {data ? <RewardsBody data={data} /> : null}
    </section>
  );
}

function RewardsBody({ data }: { data: CitizenRewards }) {
  const { t } = useI18n();
  const prompt = !data.participation.eligible
    ? data.participation.optedIn
      ? t('rewards.completeProfile')
      : t('rewards.privateBoard')
    : null;
  return (
    <>
      {prompt ? (
        <div className="notice" role="status">
          {prompt} <Link to="/profile">{t('profile.title')}</Link>
        </div>
      ) : null}
      <div className="settings-card">
        <p>
          <strong>{t('rewards.confirmed')}</strong>: {data.confirmedPoints}
        </p>
        <p>
          <strong>{t('rewards.pending')}</strong>: {data.pendingPoints}
        </p>
        <p>
          <strong>{t('rewards.monthly')}</strong>: {data.monthlyPoints}
        </p>
        <p>
          <strong>{t('rewards.level')}</strong>: {data.levelTitle}
        </p>
        <p>
          <strong>{t('rewards.rank')}</strong>: {data.privateRankAllTime ?? '—'}
        </p>
        {data.publicRankAllTime ? (
          <p>
            <strong>{t('rewards.publicRank')}</strong>: {data.publicRankAllTime}
          </p>
        ) : null}
        <p>
          {data.pointsToNextLevel != null && data.nextLevelTitle
            ? t('rewards.nextLevel', {
                points: data.pointsToNextLevel,
                title: data.nextLevelTitle,
              })
            : t('rewards.maxLevel')}
        </p>
        <h2>{t('rewards.badges')}</h2>
        {data.badges.length ? (
          <ul>
            {data.badges.map((badge) => (
              <li key={badge}>{badge}</li>
            ))}
          </ul>
        ) : (
          <p>{t('rewards.noBadges')}</p>
        )}
      </div>
      {data.confirmedPoints === 0 ? (
        <div className="notice" role="status">
          <strong>{t('rewards.emptyTitle')}</strong>
          <p>{t('rewards.emptyBody')}</p>
        </div>
      ) : null}
      <div className="settings-card">
        <h2>{t('rewards.recent')}</h2>
        {data.recentEvents.length ? (
          <ul>
            {data.recentEvents.map((event) => (
              <li key={`${event.createdAt}-${event.reason}-${event.delta}`}>
                {event.delta > 0 ? '+' : ''}
                {event.delta} · {t(`rewards.reason.${event.reason}`)}
                {event.ticketNumber ? ` · ${event.ticketNumber}` : ''}
              </li>
            ))}
          </ul>
        ) : (
          <p>{t('rewards.emptyBody')}</p>
        )}
      </div>
      <p className="helper">{t('rewards.recognitionNote')}</p>
    </>
  );
}
