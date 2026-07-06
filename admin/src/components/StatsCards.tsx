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
    key: 'resolved' as const,
    label: 'Resolved',
    Icon: IconCheckCircle,
    accent: 'stats-card--green',
  },
];

export function StatsCards({ stats }: StatsCardsProps) {
  return (
    <div className="stats-cards" role="group" aria-label="Ticket summary">
      {CARDS.map((card) => (
        <div key={card.key} className={`stats-card ${card.accent}`}>
          <div className="stats-card__icon" aria-hidden="true">
            <card.Icon />
          </div>
          <div className="stats-card__body">
            <p className="stats-card__value">{stats[card.key]}</p>
            <p className="stats-card__label">{card.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
