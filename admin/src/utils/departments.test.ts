import { describe, expect, it } from 'vitest';

import {
  DEPARTMENT_OPTIONS,
  departmentOptionsForSession,
} from '@/utils/departments';

const ROADS = 'd1111111-1111-1111-1111-111111111111';
const WASTE = 'd2222222-2222-2222-2222-222222222222';

describe('departmentOptionsForSession', () => {
  it('returns the full catalog when the session is unscoped', () => {
    expect(departmentOptionsForSession(null)).toEqual(DEPARTMENT_OPTIONS);
    expect(departmentOptionsForSession(undefined)).toEqual(DEPARTMENT_OPTIONS);
    expect(departmentOptionsForSession([])).toEqual(DEPARTMENT_OPTIONS);
  });

  it('keeps only departments the staff member is scoped to', () => {
    expect(departmentOptionsForSession([ROADS, WASTE]).map((option) => option.departmentId)).toEqual(
      [ROADS, WASTE],
    );
  });

  it('falls back to the catalog when every scoped id is unknown', () => {
    expect(departmentOptionsForSession(['unknown-department'])).toEqual(DEPARTMENT_OPTIONS);
  });
});
