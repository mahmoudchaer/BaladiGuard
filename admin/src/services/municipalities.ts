import { config } from '@/services/config';
import { clearStoredStaffSession, getStaffAuthHeaders } from '@/services/auth';

export type ServiceDomain =
  | 'roads'
  | 'waste'
  | 'lighting'
  | 'water'
  | 'noise'
  | 'traffic'
  | 'drainage'
  | 'facilities'
  | 'electricity';

export type MunicipalityProfile = {
  municipalityId: string;
  name: string;
  legalName: string | null;
  description: string;
  city: string | null;
  governorate: string | null;
  serviceDomains: ServiceDomain[];
  bounds: {
    minLatitude: number;
    maxLatitude: number;
    minLongitude: number;
    maxLongitude: number;
  };
  active: boolean;
  profileVersion: number;
  createdAt: string;
  updatedAt: string;
  departments?: Array<{
    departmentId: string;
    municipalityId: string;
    name: string;
    serviceDomain: string;
  }>;
};

export type UpsertMunicipalityInput = {
  name: string;
  legalName?: string;
  description: string;
  city?: string;
  governorate?: string;
  serviceDomains: ServiceDomain[];
  bounds: MunicipalityProfile['bounds'];
  active: boolean;
};

export type RoutingPreview = {
  decision: {
    status: string;
    municipalityId: string | null;
    suggestedMunicipalityId: string | null;
    confidence: number | null;
    method: string;
    reasonCode: string;
    reason: string;
    eligibleMunicipalityIds: string[];
  };
  eligible: MunicipalityProfile[];
};

async function throwApiError(response: Response, fallback: string): Promise<never> {
  if (response.status === 401) {
    clearStoredStaffSession();
  }
  let message = fallback;
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    if (typeof body.error?.message === 'string') {
      message = body.error.message;
    }
  } catch {
    // Keep fallback.
  }
  throw new Error(message);
}

export async function listMunicipalities(): Promise<MunicipalityProfile[]> {
  const response = await fetch(`${config.apiBaseUrl}/v1/ops/municipalities`, {
    headers: { ...getStaffAuthHeaders() },
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load municipalities.');
  }
  const body = (await response.json()) as { items?: MunicipalityProfile[] };
  return Array.isArray(body.items) ? body.items : [];
}

export async function createMunicipality(
  input: UpsertMunicipalityInput,
): Promise<MunicipalityProfile> {
  const response = await fetch(`${config.apiBaseUrl}/v1/ops/municipalities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getStaffAuthHeaders() },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to create municipality.');
  }
  return (await response.json()) as MunicipalityProfile;
}

export async function updateMunicipality(
  municipalityId: string,
  input: UpsertMunicipalityInput,
): Promise<MunicipalityProfile> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/ops/municipalities/${encodeURIComponent(municipalityId)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getStaffAuthHeaders() },
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to update municipality.');
  }
  return (await response.json()) as MunicipalityProfile;
}

export async function provisionMunicipalityAdmin(
  municipalityId: string,
  input: { username: string; name: string; email: string; password: string },
): Promise<{ staffId: string; username: string; municipalityId: string; role: string }> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/ops/municipalities/${encodeURIComponent(municipalityId)}/admin`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getStaffAuthHeaders() },
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to provision the first administrator.');
  }
  return (await response.json()) as {
    staffId: string;
    username: string;
    municipalityId: string;
    role: string;
  };
}

export async function previewMunicipalityRouting(input: {
  latitude: number;
  longitude: number;
  category?: string;
  description?: string;
}): Promise<RoutingPreview> {
  const response = await fetch(`${config.apiBaseUrl}/v1/ops/municipalities/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getStaffAuthHeaders() },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to preview routing.');
  }
  return (await response.json()) as RoutingPreview;
}

export async function overrideTicketMunicipality(
  ticketId: string,
  input: { municipalityId: string | null; reasonCode: string; note?: string },
): Promise<void> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/ops/tickets/${encodeURIComponent(ticketId)}/municipality/override`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getStaffAuthHeaders() },
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to override ticket routing.');
  }
}
