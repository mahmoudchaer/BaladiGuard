import { describe, expect, it } from 'vitest';

import {
  EMAIL_INVALID_MESSAGE,
  PUBLIC_NAME_REQUIRES_NAME_MESSAGE,
  TICKET_UPDATES_EMAIL_REQUIRED_MESSAGE,
  profileEditSchema,
  profileToEditValues,
} from '@/schemas/citizenProfileSchema';
import type { CitizenProfile } from '@/types/citizen';

const baseProfile: CitizenProfile = {
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

describe('citizenProfileSchema', () => {
  it('accepts a valid profile edit payload', () => {
    const parsed = profileEditSchema.parse({
      ...profileToEditValues(baseProfile),
      fullName: '  Ada Updated  ',
      email: 'ada@example.com',
      ticketUpdates: 'EMAIL',
      announcements: true,
      publicNameVisible: true,
    });
    expect(parsed.fullName).toBe('Ada Updated');
    expect(parsed.email).toBe('ada@example.com');
  });

  it('allows a blank optional full name', () => {
    const parsed = profileEditSchema.parse({
      ...profileToEditValues(baseProfile),
      fullName: '   ',
      publicNameVisible: false,
    });
    expect(parsed.fullName).toBe('');
  });

  it('rejects public name visibility without a full name', () => {
    const result = profileEditSchema.safeParse({
      ...profileToEditValues(baseProfile),
      fullName: '',
      publicNameVisible: true,
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe(PUBLIC_NAME_REQUIRES_NAME_MESSAGE);
  });

  it('allows nullable / blank email', () => {
    const parsed = profileEditSchema.parse({
      ...profileToEditValues(baseProfile),
      email: '   ',
      ticketUpdates: 'SMS',
    });
    expect(parsed.email.trim()).toBe('');
  });

  it('rejects invalid email and EMAIL ticket updates without email', () => {
    const invalidEmail = profileEditSchema.safeParse({
      ...profileToEditValues(baseProfile),
      email: 'not-an-email',
    });
    expect(invalidEmail.success).toBe(false);
    expect(invalidEmail.error?.issues[0]?.message).toBe(EMAIL_INVALID_MESSAGE);

    const emailRequired = profileEditSchema.safeParse({
      ...profileToEditValues(baseProfile),
      email: '',
      ticketUpdates: 'BOTH',
    });
    expect(emailRequired.success).toBe(false);
    expect(
      emailRequired.error?.issues.some(
        (issue) => issue.message === TICKET_UPDATES_EMAIL_REQUIRED_MESSAGE,
      ),
    ).toBe(true);
  });

  it('maps profile defaults with publicNameVisible off', () => {
    expect(profileToEditValues(baseProfile).publicNameVisible).toBe(false);
  });
});
