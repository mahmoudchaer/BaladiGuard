/**
 * Urgency presentation helpers.
 *
 * Bands mirror backend/app/services/urgency/score.py `_level_for_score` so the
 * compact admin label never disagrees with the stored reason text.
 */

export type UrgencyLevel = 'low' | 'medium' | 'high' | 'critical';

const URGENCY_LEVEL_LABELS: Record<UrgencyLevel, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

export function urgencyLevelForScore(score: number): UrgencyLevel {
  if (score >= 75) {
    return 'critical';
  }
  if (score >= 50) {
    return 'high';
  }
  if (score >= 25) {
    return 'medium';
  }
  return 'low';
}

/** Compact staff-facing summary, e.g. `Medium · 25/100`. */
export function formatUrgencySummary(score: number): string {
  return `${URGENCY_LEVEL_LABELS[urgencyLevelForScore(score)]} · ${score}/100`;
}
