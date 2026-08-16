import { t } from '@/i18n';
import type { TicketPriority } from '@/types/ticket';
import { formatPriority } from '@/utils/labels';
import './PriorityBadge.css';

type PriorityBadgeProps = {
  priority: TicketPriority | null;
};

const PRIORITY_CLASS: Record<TicketPriority, string> = {
  low: 'priority-badge--low',
  medium: 'priority-badge--medium',
  high: 'priority-badge--high',
  critical: 'priority-badge--critical',
};

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const className = priority
    ? `priority-badge ${PRIORITY_CLASS[priority]}`
    : 'priority-badge priority-badge--unset';

  const label = formatPriority(priority);
  return (
    <span className={className} aria-label={t('a11y.urgencyWithLabel', { urgency: label })}>
      {label}
    </span>
  );
}
