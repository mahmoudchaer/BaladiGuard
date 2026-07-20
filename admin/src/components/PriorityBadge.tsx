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

  return <span className={className}>{formatPriority(priority)}</span>;
}
