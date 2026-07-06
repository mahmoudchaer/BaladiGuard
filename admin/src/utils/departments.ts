import { DEPARTMENT_NAMES } from '@/data/departments';

export function formatDepartment(departmentId: string | null): string {
  if (!departmentId) {
    return 'Unassigned';
  }

  return DEPARTMENT_NAMES[departmentId] ?? departmentId;
}
