import { t } from '@/i18n';
import type { TicketStatus } from '@/types/ticket';

export function getCitizenNextAction(status: TicketStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return t('nextAction.SUBMITTED');
    case 'UNDER_REVIEW':
      return t('nextAction.UNDER_REVIEW');
    case 'ASSIGNED':
      return t('nextAction.ASSIGNED');
    case 'IN_PROGRESS':
      return t('nextAction.IN_PROGRESS');
    case 'RESOLVED':
      return t('nextAction.RESOLVED');
    case 'CLOSED':
      return t('nextAction.CLOSED');
    default:
      return t('nextAction.unknown');
  }
}
