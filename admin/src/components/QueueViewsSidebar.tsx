import type { QueueAttentionStats } from '@/utils/ticketStats';
import './QueueViewsSidebar.css';

export type QueueViewId = 'all' | 'critical' | 'unassigned' | 'aging' | 'high';

type QueueViewsSidebarProps = {
  activeView: QueueViewId;
  stats: QueueAttentionStats;
  totalCount: number;
  highCount: number;
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
  onViewChange,
}: QueueViewsSidebarProps) {
  const views: ViewItem[] = [
    { id: 'all', label: 'All tickets', count: totalCount },
    { id: 'critical', label: 'Critical', count: stats.critical, tone: 'critical' },
    { id: 'high', label: 'High priority', count: highCount, tone: 'warn' },
    { id: 'unassigned', label: 'Unassigned', count: stats.unassigned },
    { id: 'aging', label: 'Aging (3d+)', count: stats.aging },
  ];

  return (
    <aside className="queue-views" aria-label="Ticket views">
      <div className="queue-views__header">
        <p className="queue-views__eyebrow">Ticket views</p>
        <h2 className="queue-views__title">Needs attention</h2>
      </div>

      <div className="queue-views__list" role="group" aria-label="Ticket summary">
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
        <p className="queue-views__hint">
          Views triage the queue. Status and department filters stay available in the list toolbar.
        </p>
      </div>
    </aside>
  );
}
