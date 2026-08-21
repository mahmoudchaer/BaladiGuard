export type TicketUpdatesPreference = 'SMS' | 'EMAIL' | 'BOTH' | 'NONE';

export type NotificationPreferences = {
  ticketUpdates: TicketUpdatesPreference;
  announcements: boolean;
};

export type CitizenProfile = {
  userId: string;
  phone: string;
  phoneVerifiedAt: string;
  fullName: string | null;
  email: string | null;
  notificationPreferences: NotificationPreferences;
  publicNameVisible: boolean;
  active: boolean;
  contributionReady: boolean;
  createdAt: string;
  updatedAt: string;
};

export type CitizenOtpPurpose = 'LOGIN_OR_SIGNUP' | 'CHANGE_PHONE';

export type CitizenOtpRequestPayload = {
  phone: string;
  region?: string;
  purpose?: CitizenOtpPurpose;
};

export type CitizenOtpRequestResponse = {
  challengeId: string;
  expiresIn: number;
  message: string;
  /** Server-configured delivery hint for UI copy (`sms` | `whatsapp` | `dev`). */
  deliveryChannel?: 'sms' | 'whatsapp' | 'dev';
};

export type CitizenOtpVerifyPayload = {
  challengeId: string;
  code: string;
  fullName?: string;
};

export type CitizenOtpVerifyResponse = CitizenProfile & {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
};

export type CitizenSession = {
  accessToken: string;
  expiresAt: number;
  profile: CitizenProfile;
};

export type CitizenProfileUpdatePayload = {
  /** Omit to leave unchanged; `null` clears the optional full name. */
  fullName?: string | null;
  /** Omit to leave unchanged; `null` clears the optional email. */
  email?: string | null;
  notificationPreferences?: Partial<NotificationPreferences>;
  publicNameVisible?: boolean;
  phone?: string;
  region?: string;
  phoneChangeChallengeId?: string;
  phoneChangeCode?: string;
};
