import type { TicketStats } from '@/utils/ticketStats';
import './StatsCards.css';

type StatsCardsProps = {
  stats: TicketStats;
};

const CARDS = [
  {
    key: 'total' as const,
    label: 'Total Tickets',
    icon: '📋',
    accent: 'stats-card--blue',
  },
  {
    key: 'open' as const,
    label: 'Open Tickets',
    icon: '🔓',
    accent: 'stats-card--amber',
  },
  {
    key: 'highUrgency' as const,
    label: 'High Urgency',
    icon: '🔴',
    accent: 'stats-card--red',
  },
  {
    key: 'resolved' as const,
    label: 'Resolved',
    icon: '✅',
    accent: 'stats-card--green',
  },
];

export function StatsCards({ stats }: StatsCardsProps) {
  return (
    <div className="stats-cards" role="group" aria-label="Ticket summary">
      {CARDS.map((card) => (
        <div key={card.key} className={`stats-card ${card.accent}`}>
          <div className="stats-card__icon" aria-hidden="true">
            {card.icon}
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
