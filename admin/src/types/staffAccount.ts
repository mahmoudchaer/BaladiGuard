export type StaffAccountRole = 'municipal_staff' | 'administrator';

export type StaffAccount = {
  staffId: string;
  username: string;
  name: string;
  email: string;
  role: StaffAccountRole;
  municipalityId: string | null;
  departmentIds: string[] | null;
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type CreateStaffAccountInput = {
  username: string;
  name: string;
  email: string;
  password: string;
  role: StaffAccountRole;
  municipalityId: string | null;
  departmentIds: string[] | null;
};

export type UpdateStaffAccountInput = {
  role?: StaffAccountRole;
  municipalityId?: string | null;
  departmentIds?: string[] | null;
};
