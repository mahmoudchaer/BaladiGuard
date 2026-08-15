import React from 'react';
import { act } from 'react-test-renderer';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ExploreScreen from '../../app/(tabs)/explore';
import LoginScreen from '../../app/login';
import { PhoneEntryForm } from '@/features/citizen-auth/PhoneEntryForm';
import { OtpVerifyForm } from '@/features/citizen-auth/OtpVerifyForm';
import { ReportForm } from '@/features/citizen-report/ReportForm';
import { ProfileSummary } from '@/features/profile/ProfileSummary';
import { TrackLookupForm } from '@/features/ticket-tracking/TrackLookupForm';
import { resetLocaleForTests, setLocale, t, type AppLocale } from '@/i18n';
import { getPublicTickets, getTicketByTrackingCode } from '@/services/api/tickets';
import { renderWithProviders, renderWithProvidersAsync } from '@/test/render';
import type { CitizenProfile } from '@/types/citizen';
import type { CitizenTicketResponse } from '@/types/ticket';

vi.mock('@/services/api/tickets', () => ({
  getPublicTickets: vi.fn(),
  getTicketByTrackingCode: vi.fn(),
  getCitizenTicketHistory: vi.fn(),
  getCitizenResolutionFeedback: vi.fn(),
  submitCitizenResolutionFeedback: vi.fn(),
  submitReport: vi.fn(),
}));

vi.mock('@/services/deviceLocation', () => ({
  getCurrentDeviceLocation: vi.fn(async () => ({
    ok: false,
    reason: 'unavailable',
    message: 'Unable to read your current location right now.',
  })),
}));

vi.mock('@/services/api/locations', () => ({
  validateLocation: vi.fn(),
  defaultMapRegion: () => ({
    latitude: 33.8938,
    longitude: 35.5018,
    latitudeDelta: 0.04,
    longitudeDelta: 0.04,
  }),
  locationSourceForMapPin: () => 'GPS',
}));

vi.mock('expo-clipboard', () => ({
  setStringAsync: vi.fn(async () => true),
}));

vi.mock('expo-image-picker', () => ({
  requestMediaLibraryPermissionsAsync: vi.fn(async () => ({ granted: true })),
  requestCameraPermissionsAsync: vi.fn(async () => ({ granted: true })),
  launchImageLibraryAsync: vi.fn(async () => ({ canceled: true, assets: [] })),
  launchCameraAsync: vi.fn(async () => ({ canceled: true, assets: [] })),
}));

vi.mock('react-native-maps', () => ({
  default: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('MapView', props, children),
  Marker: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('Marker', props, children),
}));

const LOCALES: AppLocale[] = ['en', 'ar', 'fr'];

const readyProfile: CitizenProfile = {
  userId: 'usr_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T12:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'NONE', announcements: false },
  publicNameVisible: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T12:00:00Z',
  updatedAt: '2026-08-01T12:00:00Z',
};

const citizenTicket: CitizenTicketResponse = {
  ticketNumber: 'BG-2026-0042',
  trackingCode: 'AB23CD',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Hamra, Beirut' },
  department: { name: 'Road Maintenance' },
  createdAt: '2026-07-26T09:00:00Z',
  updatedAt: '2026-07-26T11:30:00Z',
  lastUpdatedAt: '2026-07-26T11:30:00Z',
  timeline: [
    { status: 'SUBMITTED', changedAt: '2026-07-26T09:00:00Z' },
    { status: 'IN_PROGRESS', changedAt: '2026-07-26T11:30:00Z' },
  ],
};

async function flush() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function hasText(screen: ReturnType<typeof renderWithProviders>, text: string): boolean {
  return screen.root.findAll((node) => node.props.children === text).length > 0;
}

describe('mobile critical-flow localization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en');
    vi.mocked(getPublicTickets).mockResolvedValue({
      items: [
        {
          ticketNumber: 'BG-2026-0001',
          status: 'IN_PROGRESS',
          category: 'road_damage',
          description: 'Large pothole near the university gate.',
          location: { addressText: 'Hamra, Beirut' },
          mapLocation: { addressText: 'Hamra, Beirut', latitude: 33.896, longitude: 35.478 },
          attribution: { displayName: 'Community member', isNamed: false },
          photoUrl: null,
          createdAt: '2026-07-07T00:00:00Z',
          updatedAt: '2026-07-07T02:00:00Z',
        },
      ],
      nextCursor: null,
      limit: 50,
    });
    vi.mocked(getTicketByTrackingCode).mockResolvedValue(citizenTicket);
  });

  afterEach(() => {
    setLocale('en');
    resetLocaleForTests();
  });

  it('localizes Explore and public-browse filter chrome in Arabic and French', async () => {
    const screen = await renderWithProvidersAsync(<ExploreScreen />);
    await flush();
    expect(hasText(screen, t('explore.title'))).toBe(true);
    expect(hasText(screen, t('explore.refine'))).toBe(true);

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      await flush();
      expect(hasText(screen, t('explore.title'))).toBe(true);
      expect(hasText(screen, t('explore.subtitle'))).toBe(true);
      expect(hasText(screen, t('explore.refine'))).toBe(true);
      expect(hasText(screen, t('explore.allStatuses'))).toBe(true);
      expect(hasText(screen, t('explore.allCategories'))).toBe(true);
    }
  });

  it('localizes phone authentication chrome in all locales', async () => {
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={vi.fn()} />);

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(hasText(screen, t('auth.phoneTitle'))).toBe(true);
      expect(hasText(screen, t('auth.sendCode'))).toBe(true);
      expect(screen.root.findByProps({ label: t('auth.phoneLabel') })).toBeTruthy();
    }
  });

  it('localizes the login route and OTP verify chrome in Arabic and French', async () => {
    const login = await renderWithProvidersAsync(<LoginScreen />);
    expect(hasText(login, t('auth.continueTitle'))).toBe(true);

    await act(async () => {
      setLocale('ar');
    });
    expect(hasText(login, t('auth.continueTitle'))).toBe(true);
    expect(hasText(login, t('auth.sendCode'))).toBe(true);

    await act(async () => {
      setLocale('fr');
    });
    expect(hasText(login, t('auth.continueTitle'))).toBe(true);

    const otp = renderWithProviders(
      <OtpVerifyForm
        challengeId="ch_1"
        expiresIn={300}
        phone="+96170123456"
        onChallengeReplaced={vi.fn()}
        onVerified={vi.fn()}
      />,
    );
    await act(async () => {
      setLocale('ar');
    });
    expect(hasText(otp, t('auth.otpTitle'))).toBe(true);
    expect(hasText(otp, t('auth.verify'))).toBe(true);
    expect(hasText(otp, t('auth.resend'))).toBe(true);

    await act(async () => {
      setLocale('fr');
    });
    expect(hasText(otp, t('auth.otpTitle'))).toBe(true);
    expect(hasText(otp, t('auth.verify'))).toBe(true);
  });

  it('localizes report form chrome in Arabic and French', async () => {
    const screen = renderWithProviders(<ReportForm />);
    expect(hasText(screen, t('report.whatsTheProblem'))).toBe(true);
    expect(screen.root.findByProps({ label: t('report.describeLabel') })).toBeTruthy();

    await act(async () => {
      setLocale('ar');
    });
    expect(hasText(screen, t('report.whatsTheProblem'))).toBe(true);
    expect(hasText(screen, t('report.continue'))).toBe(true);
    expect(hasText(screen, t('report.discardDraft'))).toBe(true);
    expect(screen.root.findByProps({ label: t('report.describeLabel') })).toBeTruthy();

    await act(async () => {
      setLocale('fr');
    });
    expect(hasText(screen, t('report.whatsTheProblem'))).toBe(true);
    expect(hasText(screen, t('report.continue'))).toBe(true);
    expect(screen.root.findByProps({ label: t('report.describeLabel') })).toBeTruthy();
  });

  it('localizes profile summary chrome in all locales', async () => {
    const screen = renderWithProviders(
      <ProfileSummary
        profile={readyProfile}
        onEdit={vi.fn()}
        onChangePhone={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(hasText(screen, t('profile.title'))).toBe(true);
      expect(hasText(screen, t('profile.edit'))).toBe(true);
      expect(hasText(screen, t('profile.changePhone'))).toBe(true);
      expect(hasText(screen, t('common.signOut'))).toBe(true);
      expect(hasText(screen, t('profile.publicHidden'))).toBe(true);
    }
  });

  it('localizes tracking lookup and result chrome in Arabic and French', async () => {
    const screen = renderWithProviders(<TrackLookupForm />);
    expect(hasText(screen, t('track.title'))).toBe(true);
    expect(hasText(screen, t('track.lookUp'))).toBe(true);

    await act(async () => {
      setLocale('ar');
    });
    expect(hasText(screen, t('track.title'))).toBe(true);
    expect(hasText(screen, t('track.lookUp'))).toBe(true);
    expect(screen.root.findByProps({ label: t('track.codeLabel') })).toBeTruthy();

    await act(async () => {
      screen.root.findByProps({ testID: 'tracking-code-input' }).props.onChangeText('AB23CD');
    });
    await act(async () => {
      screen.root
        .findAll((node) => String(node.type) === 'Button')
        .find((node) => node.props.children === t('track.lookUp'))
        ?.props.onPress();
    });
    await flush();

    expect(hasText(screen, t('track.found'))).toBe(true);
    expect(hasText(screen, t('track.whatHappensNext'))).toBe(true);
    expect(hasText(screen, t('track.timeline'))).toBe(true);
    expect(hasText(screen, t('track.lookUpAnother'))).toBe(true);

    await act(async () => {
      setLocale('fr');
    });
    expect(hasText(screen, t('track.found'))).toBe(true);
    expect(hasText(screen, t('track.timeline'))).toBe(true);
    expect(hasText(screen, t('track.lookUpAnother'))).toBe(true);
  });
});
