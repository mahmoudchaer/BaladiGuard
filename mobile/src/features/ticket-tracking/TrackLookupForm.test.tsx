import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TrackLookupForm } from '@/features/ticket-tracking/TrackLookupForm';
import {
  TRACKING_CODE_INVALID_MESSAGE,
  TRACKING_CODE_REQUIRED_MESSAGE,
} from '@/schemas/trackLookupSchema';
import { getTicketByTrackingCode } from '@/services/api/tickets';
import { renderWithProviders } from '@/test/render';
import type { CitizenTicketResponse } from '@/types/ticket';

const citizenTicket: CitizenTicketResponse = {
  ticketNumber: 'BG-2026-0042',
  trackingCode: 'AB23CD',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Hamra, Beirut' },
  createdAt: '2026-07-26T09:00:00Z',
  updatedAt: '2026-07-26T11:30:00Z',
  lastUpdatedAt: '2026-07-26T11:30:00Z',
  timeline: [
    { status: 'SUBMITTED', changedAt: '2026-07-26T09:00:00Z' },
    { status: 'IN_PROGRESS', changedAt: '2026-07-26T11:30:00Z' },
  ],
};

vi.mock('@/services/api/tickets', () => ({
  getTicketByTrackingCode: vi.fn(),
}));

function findButtonByText(screen: ReturnType<typeof renderWithProviders>, text: string) {
  const button = screen.root
    .findAll((node) => String(node.type) === 'Button')
    .find((node) => node.props.children === text);
  if (!button) {
    throw new Error(`Button not found: ${text}`);
  }
  return button;
}

function findTrackingInput(screen: ReturnType<typeof renderWithProviders>) {
  const input = screen.root.findByProps({ testID: 'tracking-code-input' });
  return input;
}

async function submitLookup(screen: ReturnType<typeof renderWithProviders>, trackingCode: string) {
  await act(async () => {
    findTrackingInput(screen).props.onChangeText(trackingCode);
  });
  await act(async () => {
    findButtonByText(screen, 'Look up report').props.onPress();
  });
}

describe('TrackLookupForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('rejects empty input without calling the API', async () => {
    const screen = renderWithProviders(<TrackLookupForm />);

    await act(async () => {
      findButtonByText(screen, 'Look up report').props.onPress();
    });

    expect(getTicketByTrackingCode).not.toHaveBeenCalled();
    expect(screen.root.findByProps({ children: TRACKING_CODE_REQUIRED_MESSAGE })).toBeTruthy();
  });

  it('rejects invalid format without calling the API', async () => {
    const screen = renderWithProviders(<TrackLookupForm />);

    await submitLookup(screen, 'AB1OCD');

    expect(getTicketByTrackingCode).not.toHaveBeenCalled();
    expect(screen.root.findByProps({ children: TRACKING_CODE_INVALID_MESSAGE })).toBeTruthy();
  });

  it('looks up a valid code and shows the citizen-safe result', async () => {
    vi.mocked(getTicketByTrackingCode).mockResolvedValueOnce(citizenTicket);
    const screen = renderWithProviders(<TrackLookupForm />);

    await submitLookup(screen, '  ab23cd  ');

    expect(getTicketByTrackingCode).toHaveBeenCalledWith('AB23CD');
    expect(screen.root.findByProps({ testID: 'track-lookup-result' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report found' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'AB23CD' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'BG-2026-0042' })).toBeTruthy();
    expect(
      screen.root.findAll((node) => node.props?.children === 'In Progress').length,
    ).toBeGreaterThan(0);
  });

  it('shows a clear non-sensitive message when the report is not found', async () => {
    vi.mocked(getTicketByTrackingCode).mockRejectedValueOnce(
      new Error("We couldn't find a report with that tracking code. Check the code and try again."),
    );
    const screen = renderWithProviders(<TrackLookupForm />);

    await submitLookup(screen, 'AB23CD');

    expect(
      screen.root.findByProps({
        children:
          "We couldn't find a report with that tracking code. Check the code and try again.",
      }),
    ).toBeTruthy();
    expect(() => screen.root.findByProps({ testID: 'track-lookup-result' })).toThrow();
  });

  it('disables submit while a lookup is in flight and does not duplicate requests', async () => {
    let resolveLookup: ((value: CitizenTicketResponse) => void) | undefined;
    vi.mocked(getTicketByTrackingCode).mockImplementationOnce(
      () =>
        new Promise<CitizenTicketResponse>((resolve) => {
          resolveLookup = resolve;
        }),
    );

    const screen = renderWithProviders(<TrackLookupForm />);

    await act(async () => {
      findTrackingInput(screen).props.onChangeText('AB23CD');
    });

    await act(async () => {
      findButtonByText(screen, 'Look up report').props.onPress();
    });

    const loadingButton = findButtonByText(screen, 'Looking up...');
    expect(loadingButton.props.disabled).toBe(true);
    expect(getTicketByTrackingCode).toHaveBeenCalledTimes(1);

    // Second press while in-flight must not start another request.
    await act(async () => {
      loadingButton.props.onPress?.();
    });
    expect(getTicketByTrackingCode).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveLookup?.(citizenTicket);
    });

    expect(screen.root.findByProps({ testID: 'track-lookup-result' })).toBeTruthy();
  });
});
