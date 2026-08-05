import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ReportForm } from '@/features/citizen-report/ReportForm';
import { renderWithProviders } from '@/test/render';
import { submitReport } from '@/services/api/tickets';
import { getCurrentDeviceLocation } from '@/services/deviceLocation';
import { validateLocation } from '@/services/api/locations';

const { getCurrentDeviceLocationMock, validateLocationMock } = vi.hoisted(() => ({
  getCurrentDeviceLocationMock: vi.fn(),
  validateLocationMock: vi.fn(),
}));

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

  it('shows validation messages when required report fields are missing', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await act(async () => {
      findButtonByText(screen, 'Submit report').props.onPress();
    });

    expect(hasText(screen, 'Please describe the issue in at least 10 characters.')).toBe(true);
    expect(hasText(screen, 'Please attach a photo of the issue.')).toBe(true);
    expect(hasText(screen, 'Enter a location or choose a sample place.')).toBe(true);
    expect(submitReport).not.toHaveBeenCalled();
  });

  it('submits a complete report and shows ticket number, id, and tracking code', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await changeText(
      screen,
      'What is the problem?',
      'Large pothole near the university gate causing traffic disruption.',
    );

    await act(async () => {
      findButtonByText(screen, 'Choose photo').props.onPress();
    });

    const locationChip = screen.root
      .findAll((node) => String(node.type) === 'Chip')
      .find((node) => node.props.children === 'AUB Main Gate');
    expect(locationChip).toBeTruthy();
    await act(async () => {
      locationChip?.props.onPress();
    });

    await act(async () => {
      findButtonByText(screen, 'Submit report').props.onPress();
    });

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
    expect(hasText(screen, 'tkt_1234567890abcdef')).toBe(true);
    expect(hasText(screen, 'ZX98YU')).toBe(true);
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
    expect(hasTextContaining(screen, 'Coordinates ready (33.89611, 35.47842) · source GPS')).toBe(
      true,
    );
  });

  it('shows the GPS unavailable fallback message when current location cannot be detected', async () => {
    const screen = renderWithProviders(<ReportForm />);

    await flushUpdates();

    expect(getCurrentDeviceLocation).toHaveBeenCalled();
    expect(hasText(screen, 'Unable to read your current location right now.')).toBe(true);
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

    await changeText(
      screen,
      'What is the problem?',
      'Large pothole near the university gate causing traffic disruption.',
    );
    await act(async () => {
      findButtonByText(screen, 'Choose photo').props.onPress();
    });
    const locationChip = screen.root
      .findAll((node) => String(node.type) === 'Chip')
      .find((node) => node.props.children === 'AUB Main Gate');
    await act(async () => {
      locationChip?.props.onPress();
    });

    await act(async () => {
      findButtonByText(screen, 'Submit report').props.onPress();
    });

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

  it('shows a failure state when report submission fails', async () => {
    vi.mocked(submitReport).mockRejectedValue(new Error('Backend unavailable.'));
    const screen = renderWithProviders(<ReportForm />);

    await changeText(
      screen,
      'What is the problem?',
      'Large pothole near the university gate causing traffic disruption.',
    );
    await act(async () => {
      findButtonByText(screen, 'Choose photo').props.onPress();
    });
    const locationChip = screen.root
      .findAll((node) => String(node.type) === 'Chip')
      .find((node) => node.props.children === 'AUB Main Gate');
    await act(async () => {
      locationChip?.props.onPress();
    });

    await act(async () => {
      findButtonByText(screen, 'Submit report').props.onPress();
    });

    expect(hasText(screen, 'Backend unavailable.')).toBe(true);
    expect(hasText(screen, 'Report submitted')).toBe(false);
  });
});
