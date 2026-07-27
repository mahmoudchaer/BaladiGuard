import React from 'react';
import { describe, expect, it } from 'vitest';

import { TicketTimeline } from '@/components/TicketTimeline';
import { renderWithProviders } from '@/test/render';
import type { TicketStatusHistoryEntry } from '@/types/ticket';
import { normalizeTimelineEvents } from '@/utils/timeline';

const populatedHistory: TicketStatusHistoryEntry[] = [
  {
    status: 'UNDER_REVIEW',
    changedAt: '2026-07-18T11:00:00Z',
    changedBy: 'staff-1',
    note: 'Accepted for review.',
  },
  {
    status: 'SUBMITTED',
    changedAt: '2026-07-18T10:00:00Z',
    changedBy: 'system',
  },
  {
    status: 'IN_PROGRESS',
    changedAt: '2026-07-18T12:00:00Z',
    changedBy: 'staff-2',
    note: 'Crew assigned.',
  },
];

describe('normalizeTimelineEvents', () => {
  it('sorts events chronologically and drops malformed entries', () => {
    const malformedHistory = [
      ...populatedHistory,
      { status: 'RESOLVED', changedAt: 'not-a-date', changedBy: 'staff-3' },
      { status: 'CLOSED', changedAt: '' },
    ] as unknown as TicketStatusHistoryEntry[];

    const events = normalizeTimelineEvents(malformedHistory);

    expect(events.map((event) => event.status)).toEqual([
      'SUBMITTED',
      'UNDER_REVIEW',
      'IN_PROGRESS',
    ]);
  });

  it('returns an empty list for missing history', () => {
    expect(normalizeTimelineEvents(undefined)).toEqual([]);
    expect(normalizeTimelineEvents(null)).toEqual([]);
    expect(normalizeTimelineEvents([])).toEqual([]);
  });
});

describe('TicketTimeline', () => {
  it('renders populated history for the citizen variant without actors', () => {
    const screen = renderWithProviders(
      <TicketTimeline history={populatedHistory} variant="citizen" />,
    );

    expect(screen.root.findByProps({ children: 'Submitted' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Under Review' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'In Progress' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Accepted for review.' })).toBeTruthy();
    expect(() => screen.root.findByProps({ children: 'Updated by staff-1' })).toThrow();
  });

  it('shows an empty state when history is missing', () => {
    const screen = renderWithProviders(<TicketTimeline history={undefined} />);

    expect(
      screen.root.findByProps({
        children: 'No status history is available for this ticket yet.',
      }),
    ).toBeTruthy();
  });

  it('handles incomplete history that only has status and timestamp', () => {
    const screen = renderWithProviders(
      <TicketTimeline
        history={[{ status: 'SUBMITTED', changedAt: '2026-07-18T10:00:00Z' }]}
        variant="staff"
      />,
    );

    expect(screen.root.findByProps({ children: 'Submitted' })).toBeTruthy();
    expect(() => screen.root.findByProps({ children: 'Updated by system' })).toThrow();
  });
});
