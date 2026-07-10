import type { TicketStatus } from '@/types/ticket';
import { formatStatus } from '@/utils/labels';
import './StatusBadge.css';

type StatusBadgeProps = {
  status: TicketStatus;
};

const STATUS_CLASS: Record<TicketStatus, string> = {
  SUBMITTED: 'status-badge--submitted',
  UNDER_REVIEW: 'status-badge--under-review',
  ASSIGNED: 'status-badge--assigned',
  IN_PROGRESS: 'status-badge--in-progress',
  RESOLVED: 'status-badge--resolved',
  CLOSED: 'status-badge--closed',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge ${STATUS_CLASS[status]}`}>{formatStatus(status)}</span>;
}
