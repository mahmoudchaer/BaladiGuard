import type { TicketStatus } from '@/types/ticket';

export function getCitizenNextAction(status: TicketStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return 'Your report was received and will be reviewed by municipal staff.';
    case 'UNDER_REVIEW':
      return 'Municipal staff are reviewing the report details and category.';
    case 'ASSIGNED':
      return 'The responsible department has been assigned and will plan the next step.';
    case 'IN_PROGRESS':
      return 'The assigned team is working on the issue and will update the status when done.';
    case 'RESOLVED':
      return 'The issue has been marked resolved. No further action is expected right now.';
    case 'CLOSED':
      return 'This report is closed and kept for your records.';
    default:
      return 'Check back later for the next status update.';
  }
}
