import { config } from '@/services/config';

const CATEGORY_PLACEHOLDER_COLORS: Record<string, string> = {
  road_damage: '4a5568',
  waste: '2f855a',
  street_lighting: 'd69e2e',
  water_leak: '3182ce',
  sidewalk_damage: '718096',
  drainage: '2c5282',
  noise: '805ad5',
  traffic_signal: 'c05621',
  public_facilities: '38a169',
  PENDING_CLASSIFICATION: '64748b',
};

/**
 * Resolves a display URL for a ticket image.
 * Mock mode uses a deterministic placeholder; API mode will use storage/CDN URLs later.
 */
export function getTicketImageUrl(imageObjectKey: string, category: string): string {
  if (!config.useMockData) {
    return `${config.apiBaseUrl}/v1/uploads/${encodeURIComponent(imageObjectKey)}`;
  }

  const color = CATEGORY_PLACEHOLDER_COLORS[category] ?? '64748b';
  const label = encodeURIComponent(imageObjectKey.split('/').pop() ?? 'report');
  return `https://placehold.co/800x500/${color}/ffffff?text=${label}`;
}
