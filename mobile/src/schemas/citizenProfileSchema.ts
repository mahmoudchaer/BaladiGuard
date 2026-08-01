import { z } from 'zod';

import { FULL_NAME_LENGTH_MESSAGE, FULL_NAME_REQUIRED_MESSAGE } from '@/schemas/citizenOtpSchema';
import type { CitizenProfile, TicketUpdatesPreference } from '@/types/citizen';

export const EMAIL_INVALID_MESSAGE = 'Enter a valid email address, or leave it blank.';
export const EMAIL_NOT_LOGIN_MESSAGE =
  'Email is optional for notifications only. It is not used to sign in or recover your phone.';
export const TICKET_UPDATES_EMAIL_REQUIRED_MESSAGE =
  'Add an email before choosing email ticket updates.';
export const PUBLIC_NAME_VISIBLE_HELP =
  'When enabled, your current full name appears on owned reports. Changing this preference or your name applies dynamically to existing and future owned reports. Default is off (Anonymous).';

const ticketUpdatesValues = ['SMS', 'EMAIL', 'BOTH', 'NONE'] as const;

export const profileEditSchema = z
  .object({
    fullName: z
      .string()
      .trim()
      .superRefine((value, ctx) => {
        if (!value) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: FULL_NAME_REQUIRED_MESSAGE,
          });
          return;
        }
        if (value.length > 120) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: FULL_NAME_LENGTH_MESSAGE,
          });
        }
      }),
    email: z.string(),
    ticketUpdates: z.enum(ticketUpdatesValues),
    announcements: z.boolean(),
    publicNameVisible: z.boolean(),
  })
  .superRefine((data, ctx) => {
    const trimmedEmail = data.email.trim();
    if (trimmedEmail) {
      const emailOk = z.string().email().safeParse(trimmedEmail).success;
      if (!emailOk) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: EMAIL_INVALID_MESSAGE,
          path: ['email'],
        });
      }
    }

    if (
      (data.ticketUpdates === 'EMAIL' || data.ticketUpdates === 'BOTH') &&
      !trimmedEmail
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: TICKET_UPDATES_EMAIL_REQUIRED_MESSAGE,
        path: ['ticketUpdates'],
      });
    }
  });

export type ProfileEditValues = z.infer<typeof profileEditSchema>;

export function profileToEditValues(profile: CitizenProfile): ProfileEditValues {
  return {
    fullName: profile.fullName ?? '',
    email: profile.email ?? '',
    ticketUpdates: profile.notificationPreferences.ticketUpdates,
    announcements: profile.notificationPreferences.announcements,
    publicNameVisible: profile.publicNameVisible,
  };
}

export const TICKET_UPDATES_OPTIONS: {
  value: TicketUpdatesPreference;
  label: string;
}[] = [
  { value: 'NONE', label: 'None' },
  { value: 'SMS', label: 'SMS' },
  { value: 'EMAIL', label: 'Email' },
  { value: 'BOTH', label: 'SMS + Email' },
];
