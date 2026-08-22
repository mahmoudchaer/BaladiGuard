export type TicketUpdatesPreference = 'SMS' | 'EMAIL' | 'BOTH' | 'NONE';

export type LegalAcceptance = {
  termsVersion: string;
  privacyVersion: string;
  acceptableUseVersion: string;
  acceptedAt: string;
  locale?: string | null;
  source: 'otp_verify' | 'profile' | 'reacceptance';
};

export type CitizenProfile = {
  userId: string;
  phone: string;
  phoneVerifiedAt: string;
  fullName: string | null;
  email: string | null;
  notificationPreferences: {
    ticketUpdates: TicketUpdatesPreference;
    announcements: boolean;
  };
  publicNameVisible: boolean;
  leaderboardOptIn: boolean;
  active: boolean;
  contributionReady: boolean;
  legalAcceptance?: LegalAcceptance | null;
  legalAcceptanceRequired?: boolean;
  createdAt: string;
  updatedAt: string;
};

export type OtpChallenge = {
  challengeId: string;
  expiresIn: number;
  message: string;
  deliveryChannel?: 'sms' | 'whatsapp' | 'dev';
};

export type CitizenProfilePatch = {
  fullName?: string | null;
  email?: string | null;
  notificationPreferences?: Partial<CitizenProfile['notificationPreferences']>;
  publicNameVisible?: boolean;
  leaderboardOptIn?: boolean;
  phone?: string;
  region?: string;
  phoneChangeChallengeId?: string;
  phoneChangeCode?: string;
};

export type OtpVerifyOptions = {
  acceptLegal: boolean;
  legalLocale?: string;
};

export type LegalAcceptanceRequest = {
  acceptLegal: true;
  locale?: string;
};

export type CitizenDeleteResponse = {
  status: 'deleted';
  userId: string;
  deletedAt: string;
};
