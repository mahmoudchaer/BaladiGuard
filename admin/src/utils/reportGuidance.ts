import type { TicketStatus } from '@/types/ticket';

export function getStaffNextAction(status: TicketStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return 'Review intake details, confirm the category, and assign the responsible department.';
    case 'UNDER_REVIEW':
      return 'Complete staff review, then move the ticket to the responsible department.';
    case 'ASSIGNED':
      return 'The assigned department should start work or update the ticket if work has begun.';
    case 'IN_PROGRESS':
      return 'Monitor progress and mark the ticket resolved when field work is complete.';
    case 'RESOLVED':
      return 'Confirm the resolution is accepted, then close the ticket when appropriate.';
    case 'CLOSED':
      return 'No workflow action is expected unless the report needs to be reopened.';
    default:
      return 'No next action is available for this status.';
  }
}
