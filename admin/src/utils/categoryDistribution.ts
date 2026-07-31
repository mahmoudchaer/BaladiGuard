import type { Ticket } from '@/types/ticket';

export type CategoryDistributionItem = {
  category: string;
  count: number;
  percentage: number;
};

export function getCategoryDistribution(tickets: Ticket[]): CategoryDistributionItem[] {
  const counts = new Map<string, number>();
  tickets.forEach((ticket) => counts.set(ticket.category, (counts.get(ticket.category) ?? 0) + 1));
  const total = tickets.length;

  return [...counts.entries()]
    .map(([category, count]) => ({
      category,
      count,
      percentage: total > 0 ? Math.round((count / total) * 100) : 0,
    }))
    .sort((a, b) => b.count - a.count || a.category.localeCompare(b.category));
}
