import type { CitizenProfile } from '@/types/citizen';
import type {
  CitizenTicketHistoryResponse,
  CitizenTicketResponse,
  PublicTicketListResponse,
  PublicTicketMapViewportResponse,
  PublicTicketResponse,
  SubmitTicketResponse,
} from '@/types/ticket';

/** Canonical public/citizen shapes from docs/MVP_API_CONTRACT.md — no staff fields. */

export const FORBIDDEN_PUBLIC_KEYS = [
  'ticketId',
  'trackingCode',
  'ownerUserId',
  'contact',
  'imageObjectKey',
  'imageUrl',
  'publicImageObjectKey',
  'auditHistory',
  'statusHistory',
] as const;

export const FORBIDDEN_TRACK_KEYS = [
  'ticketId',
  'ownerUserId',
  'contact',
  'imageObjectKey',
  'imageUrl',
  'publicImageObjectKey',
  'auditHistory',
  'resolutionReasonCode',
  'resolutionNote',
  'closureReasonCode',
  'closureNote',
  'outcome',
] as const;

export const publicTicketFixture: PublicTicketResponse = {
  ticketNumber: 'BG-100001',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  description: 'Large pothole near campus gate.',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  mapLocation: {
    addressText: 'Near AUB Main Gate, Beirut',
    latitude: 33.9,
    longitude: 35.482,
  },
  department: { name: 'Roads' },
  attribution: { displayName: 'Community member', isNamed: false },
  photoUrl: 'https://cdn.example/redacted.jpg',
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-02T12:00:00Z',
};

export const publicListFixture: PublicTicketListResponse = {
  items: [publicTicketFixture],
  nextCursor: null,
  limit: 20,
};

export const publicMapFixture: PublicTicketMapViewportResponse = {
  markers: [
    {
      ticketNumber: 'BG-100001',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      addressText: 'Near AUB Main Gate, Beirut',
      latitude: 33.9,
      longitude: 35.482,
    },
  ],
  clusters: [{ id: 'c1', latitude: 33.9, longitude: 35.482, count: 2 }],
  limit: 200,
  truncated: false,
  zoom: 15,
};

export const trackFixture: CitizenTicketResponse = {
  ticketNumber: 'BG-100001',
  trackingCode: 'ABC234',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  department: { name: 'Roads' },
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-02T12:00:00Z',
  lastUpdatedAt: '2026-08-02T12:00:00Z',
  timeline: [
    { status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' },
    { status: 'IN_PROGRESS', changedAt: '2026-08-02T12:00:00Z' },
  ],
  outcomeMessage: null,
};

/** Resolved tracking payload with the current backend citizen-safe outcome message. */
export const resolvedTrackFixture: CitizenTicketResponse = {
  ticketNumber: 'BG-100003',
  trackingCode: 'RES234',
  status: 'RESOLVED',
  category: 'road_damage',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  department: { name: 'Roads' },
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-04T12:00:00Z',
  lastUpdatedAt: '2026-08-04T12:00:00Z',
  timeline: [
    { status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' },
    { status: 'IN_PROGRESS', changedAt: '2026-08-02T12:00:00Z' },
    { status: 'RESOLVED', changedAt: '2026-08-04T12:00:00Z' },
  ],
  outcomeMessage: 'The reported issue has been resolved.',
};

/** Staff-only fields the current tracking API must never expose to citizens. */
export const leakedResolvedTrackPayload = {
  ...resolvedTrackFixture,
  ticketId: 'secret-ticket-id',
  resolutionReasonCode: 'WORK_COMPLETED',
  resolutionNote: 'Used the private crew address.',
  closureReasonCode: 'CONFIRMED_COMPLETE',
  closureNote: 'Internal close note',
  outcome: { code: 'WORK_COMPLETED', privateNote: 'do not show' },
};

export const historyFixture: CitizenTicketHistoryResponse = {
  items: [
    {
      trackingCode: 'ABC234',
      status: 'RESOLVED',
      category: 'road_damage',
      locationAddress: 'Near AUB Main Gate, Beirut',
      submittedAt: '2026-08-01T10:00:00Z',
      canSubmitResolutionFeedback: true,
      resolutionFeedbackStatus: null,
    },
  ],
  nextCursor: null,
  limit: 20,
};

export const profileFixture: CitizenProfile = {
  userId: 'cit_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T00:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'SMS', announcements: false },
  publicNameVisible: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T00:00:00Z',
  updatedAt: '2026-08-01T00:00:00Z',
};

export const submitFixture: SubmitTicketResponse = {
  ticketId: 'tkt_1',
  ticketNumber: 'BG-100099',
  trackingCode: 'XYZ789',
  status: 'SUBMITTED',
  message: 'Report received.',
  createdAt: '2026-08-16T00:00:00Z',
};
