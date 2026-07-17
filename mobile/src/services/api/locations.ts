import { appConfig } from '@/services/config';
import { getClientHeaders, parseApiError } from '@/services/api/http';
import type { LocationSource, ReportLocation } from '@/types/ticket';
import { PLACEHOLDER_LOCATIONS } from '@/constants/locations';

export type ValidateLocationRequest = {
  addressText?: string;
  latitude?: number;
  longitude?: number;
};

export type ValidateLocationResponse = {
  success: boolean;
  location?: ReportLocation;
  message?: string;
};

function normalizeQuery(text: string): string {
  return text.trim().toLowerCase();
}

function findMockPlace(request: ValidateLocationRequest): ReportLocation | null {
  if (request.addressText) {
    const query = normalizeQuery(request.addressText);
    const match = PLACEHOLDER_LOCATIONS.find((place) => {
      const haystack = `${place.label} ${place.addressText}`.toLowerCase();
      return haystack.includes(query) || query.includes(place.label.toLowerCase());
    });
    if (!match) {
      return null;
    }
    return {
      latitude: match.latitude,
      longitude: match.longitude,
      addressText: match.addressText,
      source: 'MANUAL',
    };
  }

  if (request.latitude === undefined || request.longitude === undefined) {
    return null;
  }

  let nearest = PLACEHOLDER_LOCATIONS[0];
  let nearestDistance = Number.POSITIVE_INFINITY;
  for (const place of PLACEHOLDER_LOCATIONS) {
    const distance =
      Math.abs(place.latitude - request.latitude) + Math.abs(place.longitude - request.longitude);
    if (distance < nearestDistance) {
      nearest = place;
      nearestDistance = distance;
    }
  }

  return {
    latitude: request.latitude,
    longitude: request.longitude,
    addressText: nearest.addressText,
    source: 'GPS',
  };
}

export async function validateLocation(
  request: ValidateLocationRequest,
): Promise<ValidateLocationResponse> {
  if (appConfig.enableMockApi) {
    const location = findMockPlace(request);
    if (!location) {
      throw new Error(
        'We could not find that address. Try a Beirut landmark or choose a map point.',
      );
    }
    return {
      success: true,
      location,
      message: 'Location validated successfully.',
    };
  }

  const response = await fetch(`${appConfig.apiBaseUrl}/locations/validate`, {
    method: 'POST',
    headers: {
      ...getClientHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to validate that location right now.');
    throw new Error(message);
  }

  return response.json() as Promise<ValidateLocationResponse>;
}

export function defaultMapRegion(location?: { latitude?: number; longitude?: number }): {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
} {
  return {
    latitude: location?.latitude ?? 33.8938,
    longitude: location?.longitude ?? 35.5018,
    latitudeDelta: 0.04,
    longitudeDelta: 0.04,
  };
}

export function locationSourceForMapPin(_existing?: LocationSource): LocationSource {
  // Map taps are user-selected pins, not sample placeholders.
  return 'GPS';
}
