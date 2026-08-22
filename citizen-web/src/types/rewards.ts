export type RewardsPeriod = 'all-time' | 'monthly';

export type CitizenRewardReason =
  'accepted' | 'in_progress' | 'resolved' | 'supporting' | 'reviewing' | 'adjusted' | 'adjustment';

export type RewardParticipation = {
  optedIn: boolean;
  publicNameVisible: boolean;
  hasDisplayName: boolean;
  eligible: boolean;
  missing: string[];
};

export type CitizenRewardEvent = {
  createdAt: string;
  delta: number;
  reason: CitizenRewardReason;
  credit: 'pending' | 'confirmed';
  ticketNumber: string | null;
};

export type CitizenRewards = {
  ruleVersion: string;
  confirmedPoints: number;
  pendingPoints: number;
  monthlyPoints: number;
  monthlyPeriod: string;
  levelId: string;
  levelTitle: string;
  nextLevelId: string | null;
  nextLevelTitle: string | null;
  pointsToNextLevel: number | null;
  badges: string[];
  privateRankAllTime: number | null;
  privateRankMonthly: number | null;
  publicRankAllTime: number | null;
  publicRankMonthly: number | null;
  participation: RewardParticipation;
  recentEvents: CitizenRewardEvent[];
  recognitionOnly: boolean;
};

export type PublicLeaderboardEntry = {
  rank: number;
  displayName: string;
  points: number;
  levelTitle: string;
};

export type PublicLeaderboard = {
  period: RewardsPeriod;
  periodKey: string;
  items: PublicLeaderboardEntry[];
  nextCursor: string | null;
  limit: number;
  ruleVersion: string;
  recognitionOnly: boolean;
};
