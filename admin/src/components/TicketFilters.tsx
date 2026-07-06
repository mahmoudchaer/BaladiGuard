import type { TicketStatus } from '@/types/ticket';
import type { StatusFilter } from '@/utils/ticketStats';
import { formatStatus } from '@/utils/labels';
import { IconSearch } from '@/components/icons';
import './TicketFilters.css';

type TicketFiltersProps = {
  searchQuery: string;
  statusFilter: StatusFilter;
  resultCount: number;
  totalCount: number;
  onSearchChange: (value: string) => void;
  onStatusChange: (status: StatusFilter) => void;
};

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'SUBMITTED', label: 'Submitted' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
  { value: 'RESOLVED', label: 'Resolved' },
];

export function TicketFilters({
  searchQuery,
  statusFilter,
  resultCount,
  totalCount,
  onSearchChange,
  onStatusChange,
}: TicketFiltersProps) {
  return (
    <div className="ticket-filters">
      <div className="ticket-filters__search-wrap">
        <span className="ticket-filters__search-icon" aria-hidden="true">
          <IconSearch />
        </span>
        <input
          type="search"
          className="ticket-filters__search"
          placeholder="Search by ticket ID, location, or description…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          aria-label="Search tickets"
        />
      </div>

      <div className="ticket-filters__pills" role="group" aria-label="Filter by status">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`ticket-filters__pill${
              statusFilter === opt.value ? ' ticket-filters__pill--active' : ''
            }`}
            onClick={() => onStatusChange(opt.value)}
            aria-pressed={statusFilter === opt.value}
          >
            {opt.value === 'ALL' ? opt.label : formatStatus(opt.value as TicketStatus)}
          </button>
        ))}
      </div>

      <p className="ticket-filters__count" aria-live="polite">
        Showing <strong>{resultCount}</strong> of {totalCount} tickets
      </p>
    </div>
  );
}
