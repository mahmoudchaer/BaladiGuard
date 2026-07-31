import type { Ticket } from '@/types/ticket';
import { formatCategory } from '@/utils/labels';
import { getCategoryDistribution } from '@/utils/categoryDistribution';
import './CategoryDistributionChart.css';

type CategoryDistributionChartProps = { tickets: Ticket[] };

function categoryClass(category: string) {
  return category.replace(/_/g, '-').replace(/[^a-z0-9-]/gi, '');
}

export function CategoryDistributionChart({ tickets }: CategoryDistributionChartProps) {
  const distribution = getCategoryDistribution(tickets);
  const maxCount = distribution[0]?.count ?? 0;

  return (
    <section className="category-chart" aria-labelledby="category-chart-title">
      <div className="category-chart__header">
        <div>
          <p className="category-chart__eyebrow">Demand mix</p>
          <h2 id="category-chart-title">Reports by category</h2>
        </div>
        <span className="category-chart__total">{tickets.length} total</span>
      </div>
      {distribution.length === 0 ? (
        <div className="category-chart__empty">
          <span className="category-chart__empty-mark" aria-hidden="true">
            —
          </span>
          <p>No category data yet</p>
          <span>New citizen reports will appear here.</span>
        </div>
      ) : (
        <div className="category-chart__rows">
          {distribution.map((item) => (
            <div className="category-chart__row" key={item.category}>
              <div className="category-chart__label">
                <span
                  className={`category-chart__dot category-chart__dot--${categoryClass(item.category)}`}
                  aria-hidden="true"
                />
                <span>{formatCategory(item.category)}</span>
                <strong>{item.count}</strong>
              </div>
              <div
                className="category-chart__track"
                role="meter"
                aria-label={`${formatCategory(item.category)} tickets`}
                aria-valuemin={0}
                aria-valuemax={maxCount}
                aria-valuenow={item.count}
              >
                <span
                  className={`category-chart__bar category-chart__bar--${categoryClass(item.category)}`}
                  style={{ width: `${Math.max((item.count / maxCount) * 100, 3)}%` }}
                />
              </div>
              <span className="category-chart__percentage">{item.percentage}%</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
