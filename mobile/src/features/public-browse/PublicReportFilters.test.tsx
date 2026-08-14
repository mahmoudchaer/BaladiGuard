import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { PublicReportFilters } from '@/features/public-browse/PublicReportFilters';
import { renderWithProviders } from '@/test/render';
import { touchTargetMin } from '@/theme';

function flattenedStyle(style: unknown): Record<string, unknown> {
  if (Array.isArray(style)) {
    return Object.assign({}, ...style.map(flattenedStyle));
  }
  return style && typeof style === 'object' ? (style as Record<string, unknown>) : {};
}

describe('PublicReportFilters', () => {
  it('keeps status and category chips at the shared accessible touch-target size', () => {
    const screen = renderWithProviders(
      <PublicReportFilters
        filters={{ status: 'ALL', category: 'ALL' }}
        categories={['ROAD_DAMAGE']}
        onChange={vi.fn()}
      />,
    );

    for (const testID of ['public-filter-status-ALL', 'public-filter-category-ROAD_DAMAGE']) {
      const pressable = screen.root.findByProps({ testID });
      const animatedView = pressable.find((node) => String(node.type) === 'AnimatedView');
      expect(flattenedStyle(animatedView.props.style).minHeight).toBe(touchTargetMin);
    }
  });
});
