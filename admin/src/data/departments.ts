/**
 * Reference department names aligned with backend seed data (departments.json).
 * Used to display human-readable department labels from departmentId.
 */
export const DEPARTMENT_NAMES: Record<string, string> = {
  'd1111111-1111-1111-1111-111111111111': 'Road Maintenance',
  'd2222222-2222-2222-2222-222222222222': 'Waste Management',
  'd3333333-3333-3333-3333-333333333333': 'Street Lighting',
  'd4444444-4444-4444-4444-444444444444': 'Water Services',
  'd5555555-5555-5555-5555-555555555555': 'Noise Control',
  'd6666666-6666-6666-6666-666666666666': 'Traffic Management',
  'd7777777-7777-7777-7777-777777777777': 'Drainage',
  'd8888888-8888-8888-8888-888888888888': 'Public Facilities',
  'd9999999-9999-4999-8999-999999999999': 'Water Distribution',
  'daaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa': 'Power Distribution',
  'dbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb': 'Power Distribution',
};

export const DEPARTMENT_MUNICIPALITY: Record<string, string> = {
  'd1111111-1111-1111-1111-111111111111': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd2222222-2222-2222-2222-222222222222': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd3333333-3333-3333-3333-333333333333': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd4444444-4444-4444-4444-444444444444': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd5555555-5555-5555-5555-555555555555': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd6666666-6666-6666-6666-666666666666': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd7777777-7777-7777-7777-777777777777': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd8888888-8888-8888-8888-888888888888': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'd9999999-9999-4999-8999-999999999999': 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  'daaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  'dbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb': 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
};

export const MUNICIPALITY_NAMES: Record<string, string> = {
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb': 'Beirut Municipality',
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc': 'Beirut Water Authority',
  'dddddddd-dddd-4ddd-8ddd-dddddddddddd': 'Beirut Electricity Authority',
  'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee': 'Tripoli Electricity Authority',
};

export function departmentsForMunicipality(municipalityId: string | null | undefined) {
  return Object.entries(DEPARTMENT_NAMES).filter(([id]) =>
    municipalityId ? DEPARTMENT_MUNICIPALITY[id] === municipalityId : true,
  );
}
