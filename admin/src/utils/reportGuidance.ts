import { t } from '@/i18n';
import type { TicketStatus } from '@/types/ticket';

export function getStaffNextAction(status: TicketStatus): string {
  const translated = t(`guidance.${status}`);
  return translated !== `guidance.${status}` ? translated : t('guidance.unknown');
}
