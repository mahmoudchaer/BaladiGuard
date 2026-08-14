export type TicketUpdatesPreference = 'SMS' | 'EMAIL' | 'BOTH' | 'NONE';

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
  active: boolean;
  contributionReady: boolean;
  createdAt: string;
  updatedAt: string;
};

export type OtpChallenge = { challengeId: string; expiresIn: number; message: string };

export type CitizenProfilePatch = {
  fullName?: string | null;
  email?: string | null;
  notificationPreferences?: Partial<CitizenProfile['notificationPreferences']>;
  publicNameVisible?: boolean;
  phone?: string;
  region?: string;
  phoneChangeChallengeId?: string;
  phoneChangeCode?: string;
};
