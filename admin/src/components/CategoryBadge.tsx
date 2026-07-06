import { formatCategory } from '@/utils/labels';
import './CategoryBadge.css';

const CATEGORY_ICONS: Record<string, string> = {
  road_damage: '🛣️',
  street_lighting: '💡',
  waste: '🗑️',
  water_leak: '💧',
  sidewalk_damage: '🚧',
  drainage: '🌊',
  noise: '🔊',
  traffic_signal: '🚦',
  public_facilities: '🏛️',
  PENDING_CLASSIFICATION: '❓',
};

type CategoryBadgeProps = {
  category: string;
};

export function CategoryBadge({ category }: CategoryBadgeProps) {
  const icon = CATEGORY_ICONS[category] ?? '📍';
  const slug = category.replace(/_/g, '-');

  return (
    <span className={`category-badge category-badge--${slug}`}>
      <span className="category-badge__icon" aria-hidden="true">
        {icon}
      </span>
      {formatCategory(category)}
    </span>
  );
}
