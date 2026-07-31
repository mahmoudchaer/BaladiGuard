import type { Ticket } from '@/types/ticket';
import { getDepartmentSummary } from '@/utils/departmentSummary';
import './DepartmentSummary.css';

type DepartmentSummaryProps = { tickets: Ticket[] };

export function DepartmentSummary({ tickets }: DepartmentSummaryProps) {
  const summary = getDepartmentSummary(tickets);
  const maxCount = summary[0]?.count ?? 0;

  return (
    <section className="department-summary" aria-labelledby="department-summary-title">
      <div className="department-summary__header">
        <div>
          <p className="department-summary__eyebrow">Ownership & routing</p>
          <h2 id="department-summary-title">Department workload</h2>
        </div>
        <span className="department-summary__total">{tickets.length} tickets</span>
      </div>

      {summary.length === 0 ? (
        <div className="department-summary__empty">
          <span aria-hidden="true">—</span>
          <p>No department workload yet</p>
          <small>Department assignments will appear here as reports arrive.</small>
        </div>
      ) : (
        <div className="department-summary__list">
          {summary.map((item) => (
            <div className="department-summary__item" key={item.departmentId ?? 'unassigned'}>
              <div className="department-summary__item-head">
                <div className="department-summary__name">
                  <span
                    className={`department-summary__dot${item.unassigned ? ' department-summary__dot--unassigned' : ''}`}
                    aria-hidden="true"
                  />
                  <strong>{item.name}</strong>
                  {item.unassigned && (
                    <span className="department-summary__badge">Needs routing</span>
                  )}
                </div>
                <strong className="department-summary__count">{item.count}</strong>
              </div>
              <div
                className="department-summary__track"
                role="meter"
                aria-label={`${item.name} workload`}
                aria-valuemin={0}
                aria-valuemax={maxCount}
                aria-valuenow={item.count}
              >
                <span
                  className={`department-summary__bar${item.unassigned ? ' department-summary__bar--unassigned' : ''}`}
                  style={{ width: `${Math.max((item.count / maxCount) * 100, 3)}%` }}
                />
              </div>
              <div className="department-summary__meta">
                {item.assignedCount > 0 && <span>{item.assignedCount} assigned</span>}
                {item.suggestedCount > 0 && <span>{item.suggestedCount} suggested</span>}
                {item.unassigned && <span>Awaiting department assignment</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
