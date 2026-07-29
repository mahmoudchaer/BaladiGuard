import { DEPARTMENT_NAMES } from '@/data/departments';

export type DepartmentOption = {
  departmentId: string;
  name: string;
};

/** Seeded department catalog options for staff assignment UI (issue #34). */
export const DEPARTMENT_OPTIONS: DepartmentOption[] = Object.entries(DEPARTMENT_NAMES).map(
  ([departmentId, name]) => ({ departmentId, name }),
);

export function formatDepartment(departmentId: string | null | undefined): string {
  if (!departmentId) {
    return 'Unassigned';
  }

  return DEPARTMENT_NAMES[departmentId] ?? departmentId;
}

export function isKnownDepartmentId(departmentId: string): boolean {
  return Object.prototype.hasOwnProperty.call(DEPARTMENT_NAMES, departmentId);
}
