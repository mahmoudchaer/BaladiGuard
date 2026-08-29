import { useI18n } from '@/i18n/LocaleProvider';
import type { QueueAttentionStats } from '@/utils/ticketStats';
import './QueueViewsSidebar.css';

export type QueueViewId = 'all' | 'critical' | 'unassigned' | 'aging' | 'high';

type QueueViewsSidebarProps = {
  activeView: QueueViewId;
  stats: QueueAttentionStats;
  totalCount: number;
  highCount: number;
  approximate?: boolean;
  onViewChange: (view: QueueViewId) => void;
};

type ViewItem = {
  id: QueueViewId;
  label: string;
  count: number;
  tone?: 'critical' | 'warn' | 'default';
};

export function QueueViewsSidebar({
  activeView,
  stats,
  totalCount,
  highCount,
  approximate = false,
  onViewChange,
}: QueueViewsSidebarProps) {
  const { t } = useI18n();
  const views: ViewItem[] = [
    { id: 'all', label: t('queue.all'), count: totalCount },
    { id: 'critical', label: t('queue.critical'), count: stats.critical, tone: 'critical' },
    { id: 'high', label: t('queue.high'), count: highCount, tone: 'warn' },
    { id: 'unassigned', label: t('queue.unassigned'), count: stats.unassigned },
    { id: 'aging', label: t('queue.overdue'), count: stats.aging },
  ];

  return (
    <aside className="queue-views" aria-label={t('queue.views')}>
      <div className="queue-views__header">
        <p className="queue-views__eyebrow">{t('queue.views')}</p>
        <h2 className="queue-views__title">{t('queue.needsAttention')}</h2>
        {approximate ? (
          <p className="queue-views__approx" aria-live="polite">
            {t('queue.approximate')}
          </p>
        ) : null}
      </div>

      <div className="queue-views__list" role="group" aria-label={t('queue.summary')}>
        {views.map((view) => {
          const active = activeView === view.id;
          const className = [
            'queue-views__item',
            active ? 'queue-views__item--active' : '',
            view.tone === 'critical' ? 'queue-views__item--critical' : '',
            view.tone === 'warn' ? 'queue-views__item--warn' : '',
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <button
              key={view.id}
              type="button"
              className={className}
              onClick={() => onViewChange(view.id)}
              aria-pressed={active}
            >
              {/* Count first in DOM so tests can read previousElementSibling of the label. */}
              <span className="queue-views__count">{view.count}</span>
              <span className="queue-views__label">{view.label}</span>
            </button>
          );
        })}
      </div>

      <div className="queue-views__footer">
        <p className="queue-views__hint">{t('queue.hint')}</p>
      </div>
    </aside>
  );
}
