import type { TicketPriority, TicketStatus } from '@/types/ticket';
import type {
  CategoryFilter,
  CategoryFilterOption,
  DepartmentFilter,
  StatusFilter,
  UrgencyFilter,
} from '@/utils/ticketStats';
import { DEPARTMENT_OPTIONS, formatDepartment } from '@/utils/departments';
import { formatCategory, formatPriority, formatStatus } from '@/utils/labels';
import { IconSearch } from '@/components/icons';
import './TicketFilters.css';

export type SlaFilter = 'ALL' | 'on_track' | 'due_soon' | 'overdue';

type TicketFiltersProps = {
  searchQuery: string;
  statusFilter: StatusFilter;
  categoryFilter: CategoryFilter;
  urgencyFilter: UrgencyFilter;
  departmentFilter: DepartmentFilter;
  slaFilter?: SlaFilter;
  categoryOptions: CategoryFilterOption[];
  resultCount: number;
  totalCount: number;
  isRefreshing?: boolean;
  /** When search lives in the top bar, hide the duplicate field here. */
  hideSearch?: boolean;
  onSearchChange: (value: string) => void;
  onStatusChange: (status: StatusFilter) => void;
  onCategoryChange: (category: CategoryFilter) => void;
  onUrgencyChange: (urgency: UrgencyFilter) => void;
  onDepartmentChange: (department: DepartmentFilter) => void;
  onSlaChange?: (sla: SlaFilter) => void;
  onClearFilters: () => void;
};

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'SUBMITTED', label: 'Submitted' },
  { value: 'UNDER_REVIEW', label: 'Under Review' },
  { value: 'ASSIGNED', label: 'Assigned' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'CLOSED', label: 'Closed' },
];

const URGENCY_OPTIONS: { value: UrgencyFilter; label: string }[] = [
  { value: 'ALL', label: 'All urgencies' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

const SLA_OPTIONS: { value: SlaFilter; label: string }[] = [
  { value: 'ALL', label: 'All SLA states' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'due_soon', label: 'Due soon' },
  { value: 'on_track', label: 'On track' },
];

export function TicketFilters({
  searchQuery,
  statusFilter,
  categoryFilter,
  urgencyFilter,
  departmentFilter,
  slaFilter = 'ALL',
  categoryOptions,
  resultCount,
  totalCount,
  isRefreshing = false,
  hideSearch = false,
  onSearchChange,
  onStatusChange,
  onCategoryChange,
  onUrgencyChange,
  onDepartmentChange,
  onSlaChange = () => undefined,
  onClearFilters,
}: TicketFiltersProps) {
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL' ||
    slaFilter !== 'ALL';

  const activeFilterLabels: string[] = [];
  if (statusFilter !== 'ALL') {
    activeFilterLabels.push(formatStatus(statusFilter));
  }
  if (categoryFilter !== 'ALL') {
    activeFilterLabels.push(formatCategory(categoryFilter));
  }
  if (urgencyFilter !== 'ALL') {
    activeFilterLabels.push(formatPriority(urgencyFilter));
  }
  if (departmentFilter !== 'ALL') {
    activeFilterLabels.push(formatDepartment(departmentFilter));
  }
  if (slaFilter !== 'ALL') activeFilterLabels.push(slaFilter.replace('_', ' '));
  if (searchQuery.trim()) {
    activeFilterLabels.push(`“${searchQuery.trim()}”`);
  }

  return (
    <div className={`ticket-filters${hideSearch ? ' ticket-filters--compact' : ''}`}>
      <div className="ticket-filters__toolbar">
        {!hideSearch ? (
          <div className="ticket-filters__search-wrap">
            <span className="ticket-filters__search-icon" aria-hidden="true">
              <IconSearch />
            </span>
            <input
              type="search"
              className="ticket-filters__search"
              placeholder="Search ticket #, location, or description…"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label="Search tickets"
            />
          </div>
        ) : null}

        <div className="ticket-filters__selects">
          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">Category</span>
            <select
              className="ticket-filters__select"
              value={categoryFilter}
              onChange={(e) => onCategoryChange(e.target.value)}
            >
              {categoryOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.value === 'ALL' ? opt.label : formatCategory(opt.value)}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">SLA</span>
            <select
              className="ticket-filters__select"
              value={slaFilter}
              onChange={(e) => onSlaChange(e.target.value as SlaFilter)}
            >
              {SLA_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">Urgency</span>
            <select
              className="ticket-filters__select"
              value={urgencyFilter}
              onChange={(e) => onUrgencyChange(e.target.value as UrgencyFilter)}
            >
              {URGENCY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.value === 'ALL' ? opt.label : formatPriority(opt.value as TicketPriority)}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">Department</span>
            <select
              className="ticket-filters__select"
              value={departmentFilter}
              onChange={(e) => onDepartmentChange(e.target.value as DepartmentFilter)}
            >
              <option value="ALL">All departments</option>
              {DEPARTMENT_OPTIONS.map((department) => (
                <option key={department.departmentId} value={department.departmentId}>
                  {formatDepartment(department.departmentId)}
                </option>
              ))}
            </select>
          </label>
        </div>
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

      <div className="ticket-filters__meta">
        <p className="ticket-filters__count" aria-live="polite">
          Showing <strong>{resultCount}</strong> of {totalCount} tickets
          {isRefreshing && <span className="ticket-filters__refreshing">Updating...</span>}
        </p>

        {hasActiveFilters && (
          <div className="ticket-filters__active">
            <span className="ticket-filters__active-label">Active:</span>
            <span className="ticket-filters__active-values">{activeFilterLabels.join(' · ')}</span>
            <button type="button" className="ticket-filters__clear" onClick={onClearFilters}>
              Clear all
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
