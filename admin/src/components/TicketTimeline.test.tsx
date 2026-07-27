import { screen } from '@testing-library/react';
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
      { changedAt: '2026-07-18T13:00:00Z' },
      null,
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
  it('renders populated history with status, time, actor, and note', () => {
    renderWithProviders(<TicketTimeline history={populatedHistory} variant="staff" />);

    expect(screen.getByLabelText('Ticket status timeline')).toBeInTheDocument();
    expect(screen.getByText('Submitted')).toBeInTheDocument();
    expect(screen.getByText('Under Review')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Updated by staff-1')).toBeInTheDocument();
    expect(screen.getByText('Accepted for review.')).toBeInTheDocument();
    expect(screen.getByText('Crew assigned.')).toBeInTheDocument();
  });

  it('hides staff actor details in the citizen variant', () => {
    renderWithProviders(<TicketTimeline history={populatedHistory} variant="citizen" />);

    expect(screen.queryByText(/Updated by/)).not.toBeInTheDocument();
    expect(screen.getByText('Accepted for review.')).toBeInTheDocument();
  });

  it('shows an empty state when history is missing', () => {
    renderWithProviders(<TicketTimeline history={undefined} />);

    expect(
      screen.getByText('No status history is available for this ticket yet.'),
    ).toBeInTheDocument();
  });

  it('handles incomplete history that only has status and timestamp', () => {
    renderWithProviders(
      <TicketTimeline
        history={[{ status: 'SUBMITTED', changedAt: '2026-07-18T10:00:00Z' }]}
        variant="staff"
      />,
    );

    expect(screen.getByText('Submitted')).toBeInTheDocument();
    expect(screen.queryByText(/Updated by/)).not.toBeInTheDocument();
  });
});
