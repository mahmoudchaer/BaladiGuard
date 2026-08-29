export type ResolutionFeedbackStatus = 'CONFIRMED_FIXED' | 'STILL_UNRESOLVED';
export type ResolutionFeedbackReviewStatus = 'PENDING' | 'REVIEWED';
export type ResolutionFeedbackReviewAction = 'KEEP_RESOLVED' | 'RETURN_IN_PROGRESS';

export type StaffResolutionFeedback = {
  ticketId: string;
  trackingCode: string;
  ticketStatus: string;
  status: ResolutionFeedbackStatus | null;
  note: string | null;
  submittedAt: string | null;
  reviewStatus: ResolutionFeedbackReviewStatus | null;
  reviewedAt: string | null;
  reviewedBy: string | null;
  reviewAction: ResolutionFeedbackReviewAction | null;
  needsReview: boolean;
};
