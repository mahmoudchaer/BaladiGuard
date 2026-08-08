import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ReportForm } from '@/features/citizen-report/ReportForm';
import { renderWithProviders } from '@/test/render';
import { submitReport } from '@/services/api/tickets';
import { getCurrentDeviceLocation } from '@/services/deviceLocation';
import { validateLocation } from '@/services/api/locations';

const { getCurrentDeviceLocationMock, validateLocationMock, setStringAsyncMock } = vi.hoisted(
  () => ({
    getCurrentDeviceLocationMock: vi.fn(),
    validateLocationMock: vi.fn(),
    setStringAsyncMock: vi.fn(async () => true),
  }),
);

const submitResponse = {
  ticketId: 'tkt_1234567890abcdef',
  ticketNumber: 'BG-2026-0042',
  trackingCode: 'ZX98YU',
  status: 'SUBMITTED' as const,
  message: 'Your report was submitted successfully.',
  createdAt: '2026-07-26T09:00:00Z',
};

vi.mock('@/services/config', () => ({
  appConfig: {
    apiBaseUrl: 'http://localhost:8000/v1',
    enableMockApi: false,
    appVersion: '0.1.0',
  },
}));

vi.mock('@/services/api/tickets', () => ({
  submitReport: vi.fn(),
}));

vi.mock('@/services/deviceLocation', () => ({
  getCurrentDeviceLocation: getCurrentDeviceLocationMock,
}));

vi.mock('@/services/api/locations', () => ({
  validateLocation: validateLocationMock,
  defaultMapRegion: (location?: { latitude?: number; longitude?: number }) => ({
    latitude: location?.latitude ?? 33.8938,
    longitude: location?.longitude ?? 35.5018,
    latitudeDelta: 0.04,
    longitudeDelta: 0.04,
  }),
  locationSourceForMapPin: () => 'GPS',
}));

vi.mock('expo-image-picker', () => ({
  MediaTypeOptions: { Images: 'Images' },
  requestMediaLibraryPermissionsAsync: vi.fn(async () => ({ granted: true })),
  requestCameraPermissionsAsync: vi.fn(async () => ({ granted: true })),
  launchImageLibraryAsync: vi.fn(async () => ({
    canceled: false,
    assets: [
      {
        uri: 'file:///report-photo.jpg',
        fileName: 'report-photo.jpg',
        mimeType: 'image/jpeg',
      },
    ],
  })),
  launchCameraAsync: vi.fn(async () => ({
    canceled: false,
    assets: [
      {
        uri: 'file:///camera-photo.jpg',
        fileName: 'camera-photo.jpg',
        mimeType: 'image/jpeg',
      },
    ],
  })),
}));

vi.mock('expo-clipboard', () => ({
  setStringAsync: setStringAsyncMock,
}));

vi.mock('react-native-maps', () => ({
  default: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('MapView', props, children),
  Marker: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('Marker', props, children),
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

function hasText(screen: ReturnType<typeof renderWithProviders>, text: string): boolean {
  return screen.root.findAll((node) => node.props.children === text).length > 0;
}

function textContent(value: React.ReactNode): string {
  if (Array.isArray(value)) {
    return value.map(textContent).join('');
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function hasTextContaining(screen: ReturnType<typeof renderWithProviders>, text: string): boolean {
  return screen.root.findAll((node) => textContent(node.props.children).includes(text)).length > 0;
}

async function flushUpdates() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function pressButton(screen: ReturnType<typeof renderWithProviders>, text: string) {
  await act(async () => {
    findButtonByText(screen, text).props.onPress();
  });
}

async function changeText(
  screen: ReturnType<typeof renderWithProviders>,
  label: string,
  value: string,
) {
  const input = screen.root.findByProps({ label });
  await act(async () => {
    input.props.onChangeText(value);
  });
}

/** Fills the description and advances from the details step to the photo step. */
async function completeDetailsStep(screen: ReturnType<typeof renderWithProviders>) {
  await changeText(
    screen,
    'Describe the issue',
    'Large pothole near the university gate causing traffic disruption.',
  );
  await pressButton(screen, 'Continue');
}

/** Chooses a photo and advances from the photo step to the location step. */
async function completePhotoStep(screen: ReturnType<typeof renderWithProviders>) {
  await pressButton(screen, 'Choose photo');
  await pressButton(screen, 'Continue');
}

/** Picks the AUB Main Gate placeholder and advances from the location step to review. */
async function completeLocationStep(screen: ReturnType<typeof renderWithProviders>) {
  await flushUpdates();
  const locationChip = screen.root
    .findAll((node) => String(node.type) === 'Chip')
    .find((node) => node.props.children === 'AUB Main Gate');
  expect(locationChip).toBeTruthy();
  await act(async () => {
    locationChip?.props.onPress();
  });
  await pressButton(screen, 'Continue');
}

async function completeAllStepsToReview(screen: ReturnType<typeof renderWithProviders>) {
  await completeDetailsStep(screen);
  await completePhotoStep(screen);
  await completeLocationStep(screen);
}

describe('ReportForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(submitReport).mockResolvedValue(submitResponse);
    vi.mocked(getCurrentDeviceLocation).mockResolvedValue({
      ok: false,
      reason: 'unavailable',
      message: 'Unable to read your current location right now.',
    });
    vi.mocked(validateLocation).mockResolvedValue({
      success: true,
      location: {
        latitude: 33.896112,
        longitude: 35.478419,
        addressText: 'Near AUB Main Gate, Hamra, Beirut',
        source: 'GPS',
      },
      message: 'Location validated successfully.',
    });
  });

  it('shows a validation message and blocks advancing when description is missing', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await pressButton(screen, 'Continue');

    expect(hasText(screen, 'Please describe the issue in at least 10 characters.')).toBe(true);
    // Still on the details step: the photo step's Continue action never becomes reachable.
    expect(hasText(screen, "What's the problem?")).toBe(true);
    expect(submitReport).not.toHaveBeenCalled();
  });

  it('requires a photo before advancing from the photo step', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await completeDetailsStep(screen);
    expect(hasText(screen, 'Add a photo')).toBe(true);

    await pressButton(screen, 'Continue');

    expect(hasText(screen, 'Please attach a photo of the issue.')).toBe(true);
    expect(submitReport).not.toHaveBeenCalled();
  });

  it('requires a location before advancing from the location step', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await completeDetailsStep(screen);
    await completePhotoStep(screen);
    expect(hasText(screen, 'Where is it?')).toBe(true);
    await flushUpdates();

    await pressButton(screen, 'Continue');

    expect(hasText(screen, 'Enter a location or choose a sample place.')).toBe(true);
    expect(submitReport).not.toHaveBeenCalled();
  });

  it('shows a review summary of every step before submitting', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await completeAllStepsToReview(screen);

    expect(hasText(screen, 'Review your report')).toBe(true);
    expect(
      hasTextContaining(
        screen,
        'Large pothole near the university gate causing traffic disruption.',
      ),
    ).toBe(true);
    expect(hasTextContaining(screen, 'Near AUB Main Gate, Hamra, Beirut')).toBe(true);
    expect(submitReport).not.toHaveBeenCalled();
  });

  it('lets the citizen jump back from review to edit a step, preserving prior data', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await completeAllStepsToReview(screen);

    const editButtons = screen.root
      .findAll((node) => String(node.type) === 'Button')
      .filter((node) => node.props.children === 'Edit');
    expect(editButtons.length).toBe(3);

    await act(async () => {
      editButtons[0].props.onPress();
    });

    expect(hasText(screen, "What's the problem?")).toBe(true);
    const descriptionInput = screen.root.findByProps({ label: 'Describe the issue' });
    expect(descriptionInput.props.value).toBe(
      'Large pothole near the university gate causing traffic disruption.',
    );

    // Editing from Review returns there instead of forcing the remaining wizard steps.
    expect(hasText(screen, 'Back to review')).toBe(true);
    await pressButton(screen, 'Back to review');
    expect(hasText(screen, 'Review your report')).toBe(true);
    expect(hasText(screen, 'Submit report')).toBe(true);
  });

  it('submits a complete report and shows the ticket number and tracking code, but never the internal ticket id', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await completeAllStepsToReview(screen);
    await pressButton(screen, 'Submit report');

    expect(submitReport).toHaveBeenCalledWith(
      expect.objectContaining({
        description: 'Large pothole near the university gate causing traffic disruption.',
        addressText: 'Near AUB Main Gate, Hamra, Beirut',
        latitude: 33.896112,
        longitude: 35.478419,
        locationSource: 'PLACEHOLDER',
        photoUri: 'file:///report-photo.jpg',
        photoFileName: 'report-photo.jpg',
        photoContentType: 'image/jpeg',
      }),
      expect.objectContaining({ onProgress: expect.any(Function) }),
    );
    expect(hasText(screen, 'Report submitted')).toBe(true);
    expect(hasText(screen, 'BG-2026-0042')).toBe(true);
    expect(hasText(screen, 'ZX98YU')).toBe(true);
    // Citizen-facing confirmation only — the internal ticket id must never be shown.
    expect(hasText(screen, 'tkt_1234567890abcdef')).toBe(false);
    expect(hasTextContaining(screen, 'tkt_1234567890abcdef')).toBe(false);

    expect(hasText(screen, 'Track this report')).toBe(true);
    expect(hasText(screen, 'Back to home')).toBe(true);

    await pressButton(screen, 'Copy');
    expect(setStringAsyncMock).toHaveBeenCalledWith('ZX98YU');
  });

  it('shows the GPS success state when current location is detected', async () => {
    vi.mocked(getCurrentDeviceLocation).mockResolvedValue({
      ok: true,
      coordinates: {
        latitude: 33.896112,
        longitude: 35.478419,
        accuracyMeters: 12,
      },
    });
    const screen = renderWithProviders(<ReportForm />);

    await completeDetailsStep(screen);
    await completePhotoStep(screen);
    await flushUpdates();
    await flushUpdates();

    expect(validateLocation).toHaveBeenCalledWith({
      latitude: 33.896112,
      longitude: 35.478419,
    });
    expect(
      hasText(
        screen,
        'Using your current location. You can move the pin or look up another address.',
      ),
    ).toBe(true);
    expect(hasTextContaining(screen, 'Coordinates ready (33.89611, 35.47842)')).toBe(true);
    // The technical location source is never surfaced to citizens.
    expect(hasTextContaining(screen, 'source GPS')).toBe(false);
  });

  it('shows the GPS unavailable fallback message and reveals manual entry', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await completeDetailsStep(screen);
    await completePhotoStep(screen);
    await flushUpdates();

    expect(getCurrentDeviceLocation).toHaveBeenCalled();
    expect(hasText(screen, 'Unable to read your current location right now.')).toBe(true);
    expect(screen.root.findByProps({ label: 'Address or landmark' })).toBeTruthy();
  });

  it('shows submit progress while upload and report creation are in flight', async () => {
    let resolveSubmit: (value: typeof submitResponse) => void = () => undefined;
    let reportProgress: ((phase: 'uploading-photo' | 'submitting-report') => void) | undefined;
    vi.mocked(submitReport).mockImplementation((_values, options) => {
      reportProgress = options?.onProgress;
      return new Promise((resolve) => {
        resolveSubmit = resolve;
      });
    });
    const screen = renderWithProviders(<ReportForm />);

    await completeAllStepsToReview(screen);
    await pressButton(screen, 'Submit report');

    expect(hasText(screen, 'Uploading photo...')).toBe(true);

    await act(async () => {
      reportProgress?.('submitting-report');
    });

    expect(hasText(screen, 'Submitting report...')).toBe(true);

    await act(async () => {
      resolveSubmit(submitResponse);
    });

    expect(hasText(screen, 'Report submitted')).toBe(true);
  });

  it('shows a failure state on the review step when report submission fails', async () => {
    vi.mocked(submitReport).mockRejectedValue(new Error('Backend unavailable.'));
    const screen = renderWithProviders(<ReportForm />);

    await completeAllStepsToReview(screen);
    await pressButton(screen, 'Submit report');

    expect(hasText(screen, 'Backend unavailable.')).toBe(true);
    expect(hasText(screen, 'Report submitted')).toBe(false);
    expect(hasText(screen, 'Review your report')).toBe(true);
  });
});
