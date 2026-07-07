import { formatCategory } from '@/utils/labels';
import './CategoryBadge.css';

type CategoryBadgeProps = {
  category: string;
};

export function CategoryBadge({ category }: CategoryBadgeProps) {
  const slug = category.replace(/_/g, '-');

  return (
    <span className={`category-badge category-badge--${slug}`}>
      <span className="category-badge__dot" aria-hidden="true" />
      {formatCategory(category)}
    </span>
  );
}
