import type { Ticket, TicketLocation } from '@/types/ticket';

export const BEIRUT_CENTER = {
  latitude: 33.8938,
  longitude: 35.5018,
} as const;

export function isPlottableLocation(
  location: Partial<TicketLocation> | null | undefined,
): location is TicketLocation {
  if (!location) {
    return false;
  }

  const { latitude, longitude } = location;

  if (typeof latitude !== 'number' || typeof longitude !== 'number') {
    return false;
  }

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return false;
  }

  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
    return false;
  }

  return true;
}

export function isPlottableTicket(ticket: Ticket): boolean {
  return isPlottableLocation(ticket.location);
}

export function getPlottableTickets(tickets: Ticket[]): Ticket[] {
  return tickets.filter(isPlottableTicket);
}

const EARTH_RADIUS_METERS = 6371000;

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

/** Great-circle distance in meters, or null when either point is not plottable. */
export function distanceMetersBetween(
  from: Partial<TicketLocation> | null | undefined,
  to: Partial<TicketLocation> | null | undefined,
): number | null {
  if (!isPlottableLocation(from) || !isPlottableLocation(to)) {
    return null;
  }

  const deltaLat = toRadians(to.latitude - from.latitude);
  const deltaLng = toRadians(to.longitude - from.longitude);
  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(toRadians(from.latitude)) *
      Math.cos(toRadians(to.latitude)) *
      Math.sin(deltaLng / 2) ** 2;

  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Opens Google Maps centered on the coordinates (works in browser and mobile apps). */
export function buildGoogleMapsUrl(latitude: number, longitude: number): string {
  const lat = latitude.toFixed(6);
  const lng = longitude.toFixed(6);
  return `https://www.google.com/maps?q=${lat},${lng}`;
}
