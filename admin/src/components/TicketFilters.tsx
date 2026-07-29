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

type TicketFiltersProps = {
  searchQuery: string;
  statusFilter: StatusFilter;
  categoryFilter: CategoryFilter;
  urgencyFilter: UrgencyFilter;
  departmentFilter: DepartmentFilter;
  categoryOptions: CategoryFilterOption[];
  resultCount: number;
  totalCount: number;
  onSearchChange: (value: string) => void;
  onStatusChange: (status: StatusFilter) => void;
  onCategoryChange: (category: CategoryFilter) => void;
  onUrgencyChange: (urgency: UrgencyFilter) => void;
  onDepartmentChange: (department: DepartmentFilter) => void;
};

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'SUBMITTED', label: 'Submitted' },
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

export function TicketFilters({
  searchQuery,
  statusFilter,
  categoryFilter,
  urgencyFilter,
  departmentFilter,
  categoryOptions,
  resultCount,
  totalCount,
  onSearchChange,
  onStatusChange,
  onCategoryChange,
  onUrgencyChange,
  onDepartmentChange,
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

      <p className="ticket-filters__count" aria-live="polite">
        Showing <strong>{resultCount}</strong> of {totalCount} tickets
      </p>
    </div>
  );
}
