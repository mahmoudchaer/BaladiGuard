import { describe, expect, it } from 'vitest';

import { DEPARTMENT_OPTIONS, departmentOptionsForSession } from '@/utils/departments';

const ROADS = 'd1111111-1111-1111-1111-111111111111';
const WASTE = 'd2222222-2222-2222-2222-222222222222';

describe('departmentOptionsForSession', () => {
  it('returns the full catalog when the staff role is not scoped', () => {
    expect(departmentOptionsForSession(null)).toEqual(DEPARTMENT_OPTIONS);
    expect(departmentOptionsForSession(undefined)).toEqual(DEPARTMENT_OPTIONS);
    expect(departmentOptionsForSession([])).toEqual(DEPARTMENT_OPTIONS);
  });

  it('keeps only departments the staff member is scoped to', () => {
    expect(
      departmentOptionsForSession([ROADS, WASTE], true).map((option) => option.departmentId),
    ).toEqual([ROADS, WASTE]);
  });

  it('fails closed for empty or unknown municipal staff scopes', () => {
    expect(departmentOptionsForSession([], true)).toEqual([]);
    expect(departmentOptionsForSession(['unknown-department'], true)).toEqual([]);
  });
});
