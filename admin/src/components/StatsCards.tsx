import type { TicketStats } from '@/utils/ticketStats';
import { IconAlert, IconCheckCircle, IconDocument, IconFolderOpen } from '@/components/icons';
import './StatsCards.css';

type StatsCardsProps = {
  stats: TicketStats;
};

const CARDS = [
  {
    key: 'total' as const,
    label: 'Total Tickets',
    Icon: IconDocument,
    accent: 'stats-card--neutral',
  },
  {
    key: 'open' as const,
    label: 'Open Tickets',
    Icon: IconFolderOpen,
    accent: 'stats-card--red',
  },
  {
    key: 'highUrgency' as const,
    label: 'High Urgency',
    Icon: IconAlert,
    accent: 'stats-card--amber',
  },
  {
    key: 'completed' as const,
    label: 'Completed Tickets',
    Icon: IconCheckCircle,
    accent: 'stats-card--green',
  },
];

export function StatsCards({ stats }: StatsCardsProps) {
  const completionRate = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;
  const urgencyRate = stats.total > 0 ? Math.round((stats.highUrgency / stats.total) * 100) : 0;

  return (
    <section className="stats-overview" aria-labelledby="stats-overview-title">
      <div className="stats-overview__heading">
        <div>
          <p className="stats-overview__eyebrow">Operations overview</p>
          <h2 id="stats-overview-title">Today’s ticket health</h2>
        </div>
        <p className="stats-overview__caption">Live summary of the current municipal workload</p>
      </div>
      <div className="stats-cards" role="group" aria-label="Ticket summary">
      {CARDS.map((card) => (
        <article key={card.key} className={`stats-card ${card.accent}`}>
          <div className="stats-card__icon" aria-hidden="true">
            <card.Icon />
          </div>
          <div className="stats-card__body">
            <p className="stats-card__value">{stats[card.key]}</p>
            <p className="stats-card__label">{card.label}</p>
          </div>
          <span className="stats-card__context">
            {card.key === 'completed'
              ? `${completionRate}% of all tickets`
              : card.key === 'highUrgency'
                ? `${urgencyRate}% need priority attention`
                : card.key === 'open'
                  ? `${stats.total > 0 ? Math.round((stats.open / stats.total) * 100) : 0}% of workload`
                  : 'Across all statuses'}
          </span>
        </article>
      ))}
      </div>
    </section>
  );
}
