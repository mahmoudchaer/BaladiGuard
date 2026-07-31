import type { Ticket } from '@/types/ticket';
import { DEPARTMENT_NAMES } from '@/data/departments';

export type DepartmentSummaryItem = {
  departmentId: string | null;
  name: string;
  count: number;
  assignedCount: number;
  suggestedCount: number;
  unassigned: boolean;
};

function departmentName(ticket: Ticket, id: string): string {
  if (ticket.departmentId === id && ticket.departmentName) return ticket.departmentName;
  if (ticket.departmentId === id && ticket.department?.name) return ticket.department.name;
  return DEPARTMENT_NAMES[id] ?? id;
}

export function getDepartmentSummary(tickets: Ticket[]): DepartmentSummaryItem[] {
  const groups = new Map<string, DepartmentSummaryItem>();

  for (const ticket of tickets) {
    const assignedId = ticket.departmentId;
    const suggestedId = ticket.ai?.suggestedDepartmentId ?? null;
    const id = assignedId ?? suggestedId;
    const unassigned = id === null;
    const key = id ?? 'unassigned';
    const existing = groups.get(key);

    if (existing) {
      existing.count += 1;
      if (assignedId) existing.assignedCount += 1;
      else if (suggestedId) existing.suggestedCount += 1;
      continue;
    }

    groups.set(key, {
      departmentId: id,
      name: unassigned ? 'Unassigned' : departmentName(ticket, id),
      count: 1,
      assignedCount: assignedId ? 1 : 0,
      suggestedCount: !assignedId && suggestedId ? 1 : 0,
      unassigned,
    });
  }

  return [...groups.values()].sort((a, b) => {
    if (a.unassigned !== b.unassigned) return a.unassigned ? 1 : -1;
    return b.count - a.count || a.name.localeCompare(b.name);
  });
}
