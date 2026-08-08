import type { QueueAttentionStats } from '@/utils/ticketStats';
import './QueueAttentionStrip.css';

type QueueAttentionStripProps = {
  stats: QueueAttentionStats;
  criticalActive: boolean;
  onCriticalClick: () => void;
};

export function QueueAttentionStrip({
  stats,
  criticalActive,
  onCriticalClick,
}: QueueAttentionStripProps) {
  return (
    <section className="queue-attention" aria-labelledby="queue-attention-title">
      <div className="queue-attention__intro">
        <h2 id="queue-attention-title" className="queue-attention__title">
          Needs attention
        </h2>
        <p className="queue-attention__hint">
          Critical filters the queue. Unassigned and aging are counts only — no matching filter yet.
        </p>
      </div>

      <div className="queue-attention__items" role="group" aria-label="Ticket summary">
        <button
          type="button"
          className={`queue-attention__item queue-attention__item--critical${
            criticalActive ? ' queue-attention__item--active' : ''
          }`}
          onClick={onCriticalClick}
          aria-pressed={criticalActive}
        >
          <span className="queue-attention__value">{stats.critical}</span>
          <span className="queue-attention__label">Critical</span>
        </button>

        <div className="queue-attention__item" title="Open tickets without a department">
          <span className="queue-attention__value">{stats.unassigned}</span>
          <span className="queue-attention__label">Unassigned</span>
        </div>

        <div className="queue-attention__item" title="Open tickets older than 3 days">
          <span className="queue-attention__value">{stats.aging}</span>
          <span className="queue-attention__label">Aging (3d+)</span>
        </div>
      </div>
    </section>
  );
}
