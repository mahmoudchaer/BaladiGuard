import type { TicketStatus } from '@/types/ticket';

export function statusToModifier(status: TicketStatus): string {
  return status.toLowerCase().replace(/_/g, '-');
}
