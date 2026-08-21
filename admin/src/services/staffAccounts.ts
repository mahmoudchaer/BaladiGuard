import { clearStoredStaffSession, getStaffAuthHeaders } from '@/services/auth';
import { config } from '@/services/config';
import type {
  CreateStaffAccountInput,
  StaffAccount,
  UpdateStaffAccountInput,
} from '@/types/staffAccount';

async function readError(response: Response, fallback: string): Promise<never> {
  if (response.status === 401) {
    clearStoredStaffSession();
  }
  const payload = (await response.json().catch(() => null)) as {
    error?: { message?: string };
  } | null;
  const message = payload?.error?.message;
  throw new Error(typeof message === 'string' && message.trim() ? message : fallback);
}

function headers(): HeadersInit {
  return { 'Content-Type': 'application/json', ...getStaffAuthHeaders() };
}

async function parseAccount(response: Response, fallback: string): Promise<StaffAccount> {
  if (!response.ok) {
    await readError(response, fallback);
  }
  return (await response.json()) as StaffAccount;
}

export async function listStaffAccounts(): Promise<StaffAccount[]> {
  const response = await fetch(`${config.apiBaseUrl}/v1/admin/staff-accounts`, {
    headers: getStaffAuthHeaders(),
  });
  if (!response.ok) {
    await readError(response, 'Unable to load staff accounts.');
  }
  return (await response.json()) as StaffAccount[];
}

export async function createStaffAccount(input: CreateStaffAccountInput): Promise<StaffAccount> {
  const response = await fetch(`${config.apiBaseUrl}/v1/admin/staff-accounts`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return parseAccount(response, 'Unable to create staff account.');
}

export async function updateStaffAccount(
  staffId: string,
  input: UpdateStaffAccountInput,
): Promise<StaffAccount> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/admin/staff-accounts/${encodeURIComponent(staffId)}`,
    { method: 'PATCH', headers: headers(), body: JSON.stringify(input) },
  );
  return parseAccount(response, 'Unable to update staff account.');
}

export async function setStaffAccountActive(
  staffId: string,
  active: boolean,
): Promise<StaffAccount> {
  const action = active ? 'reactivate' : 'deactivate';
  const response = await fetch(
    `${config.apiBaseUrl}/v1/admin/staff-accounts/${encodeURIComponent(staffId)}/${action}`,
    { method: 'POST', headers: getStaffAuthHeaders() },
  );
  return parseAccount(response, `Unable to ${active ? 'reactivate' : 'deactivate'} staff account.`);
}

export type StaffDepartment = {
  departmentId: string;
  municipalityId: string;
  name: string;
  description: string;
  serviceDomain: string;
};

export async function listStaffDepartments(): Promise<StaffDepartment[]> {
  const response = await fetch(`${config.apiBaseUrl}/v1/staff/departments`, {
    headers: getStaffAuthHeaders(),
  });
  if (!response.ok) {
    await readError(response, 'Unable to load departments.');
  }
  const body = (await response.json()) as { items?: StaffDepartment[] };
  return Array.isArray(body.items) ? body.items : [];
}
