import type { ContentSafetyStatus, TicketPriority, TicketStatus } from '@/types/ticket';
import { useI18n } from '@/i18n/LocaleProvider';
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
export type ContentSafetyFilter = 'ALL' | ContentSafetyStatus;

type TicketFiltersProps = {
  searchQuery: string;
  statusFilter: StatusFilter;
  categoryFilter: CategoryFilter;
  urgencyFilter: UrgencyFilter;
  departmentFilter: DepartmentFilter;
  slaFilter?: SlaFilter;
  contentSafetyFilter?: ContentSafetyFilter;
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
  onContentSafetyChange?: (status: ContentSafetyFilter) => void;
  onClearFilters: () => void;
};

const STATUS_VALUES: StatusFilter[] = [
  'ALL',
  'SUBMITTED',
  'UNDER_REVIEW',
  'ASSIGNED',
  'IN_PROGRESS',
  'RESOLVED',
  'CLOSED',
];

const URGENCY_VALUES: UrgencyFilter[] = ['ALL', 'low', 'medium', 'high', 'critical'];
const SLA_VALUES: SlaFilter[] = ['ALL', 'overdue', 'due_soon', 'on_track'];
const CONTENT_SAFETY_VALUES: ContentSafetyFilter[] = [
  'ALL',
  'review_required',
  'pending',
  'processing',
  'passed',
  'private_only',
  'rejected',
  'failed',
];

export function TicketFilters({
  searchQuery,
  statusFilter,
  categoryFilter,
  urgencyFilter,
  departmentFilter,
  slaFilter = 'ALL',
  contentSafetyFilter = 'ALL',
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
  onContentSafetyChange = () => undefined,
  onClearFilters,
}: TicketFiltersProps) {
  const { t } = useI18n();
  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL' ||
    slaFilter !== 'ALL' ||
    contentSafetyFilter !== 'ALL';

  const slaLabel =
    slaFilter === 'overdue'
      ? t('filters.overdue')
      : slaFilter === 'due_soon'
        ? t('filters.dueSoon')
        : slaFilter === 'on_track'
          ? t('filters.onTrack')
          : t('filters.allSla');

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
  if (slaFilter !== 'ALL') activeFilterLabels.push(slaLabel);
  if (contentSafetyFilter !== 'ALL') {
    activeFilterLabels.push(t(`contentSafety.status.${contentSafetyFilter}`));
  }
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
              placeholder={t('filters.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label={t('filters.search')}
            />
          </div>
        ) : null}

        <div className="ticket-filters__selects">
          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">{t('filters.category')}</span>
            <select
              className="ticket-filters__select"
              value={categoryFilter}
              onChange={(e) => onCategoryChange(e.target.value)}
            >
              {categoryOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.value === 'ALL' ? t('filters.allCategories') : formatCategory(opt.value)}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">{t('filters.sla')}</span>
            <select
              className="ticket-filters__select"
              value={slaFilter}
              onChange={(e) => onSlaChange(e.target.value as SlaFilter)}
            >
              {SLA_VALUES.map((value) => (
                <option key={value} value={value}>
                  {value === 'ALL'
                    ? t('filters.allSla')
                    : value === 'overdue'
                      ? t('filters.overdue')
                      : value === 'due_soon'
                        ? t('filters.dueSoon')
                        : t('filters.onTrack')}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">{t('filters.contentSafety')}</span>
            <select
              className="ticket-filters__select"
              value={contentSafetyFilter}
              onChange={(e) => onContentSafetyChange(e.target.value as ContentSafetyFilter)}
            >
              {CONTENT_SAFETY_VALUES.map((value) => (
                <option key={value} value={value}>
                  {value === 'ALL'
                    ? t('filters.allContentSafety')
                    : t(`contentSafety.status.${value}`)}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">{t('filters.urgency')}</span>
            <select
              className="ticket-filters__select"
              value={urgencyFilter}
              onChange={(e) => onUrgencyChange(e.target.value as UrgencyFilter)}
            >
              {URGENCY_VALUES.map((value) => (
                <option key={value} value={value}>
                  {value === 'ALL'
                    ? t('filters.allUrgencies')
                    : formatPriority(value as TicketPriority)}
                </option>
              ))}
            </select>
          </label>

          <label className="ticket-filters__select-wrap">
            <span className="ticket-filters__select-label">{t('filters.department')}</span>
            <select
              className="ticket-filters__select"
              value={departmentFilter}
              onChange={(e) => onDepartmentChange(e.target.value as DepartmentFilter)}
            >
              <option value="ALL">{t('filters.allDepartments')}</option>
              {DEPARTMENT_OPTIONS.map((department) => (
                <option key={department.departmentId} value={department.departmentId}>
                  {formatDepartment(department.departmentId)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="ticket-filters__pills" role="group" aria-label={t('filters.statusGroup')}>
        {STATUS_VALUES.map((value) => (
          <button
            key={value}
            type="button"
            className={`ticket-filters__pill${
              statusFilter === value ? ' ticket-filters__pill--active' : ''
            }`}
            onClick={() => onStatusChange(value)}
            aria-pressed={statusFilter === value}
          >
            {value === 'ALL' ? t('filters.all') : formatStatus(value as TicketStatus)}
          </button>
        ))}
      </div>

      <div className="ticket-filters__meta">
        <p className="ticket-filters__count" aria-live="polite">
          {t('filters.showing', { shown: String(resultCount), total: String(totalCount) })}
          {isRefreshing && (
            <span className="ticket-filters__refreshing">{t('filters.updating')}</span>
          )}
        </p>

        {hasActiveFilters && (
          <div className="ticket-filters__active">
            <span className="ticket-filters__active-label">{t('filters.active')}</span>
            <span className="ticket-filters__active-values">{activeFilterLabels.join(' · ')}</span>
            <button type="button" className="ticket-filters__clear" onClick={onClearFilters}>
              {t('filters.clearAll')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
