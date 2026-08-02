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
