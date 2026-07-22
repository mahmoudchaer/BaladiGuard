import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import type { Ticket } from '@/types/ticket';
import { formatCategory, formatStatus } from '@/utils/labels';
import { BEIRUT_CENTER, buildGoogleMapsUrl } from '@/utils/ticketLocation';
import 'leaflet/dist/leaflet.css';
import './TicketMap.css';

// Vite does not rewrite Leaflet's default icon URLs; set them explicitly.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

type TicketMapProps = {
  tickets: Ticket[];
  /** Compact map for ticket detail; overview is the full Map View. */
  variant?: 'overview' | 'detail';
};

function FitTicketBounds({
  tickets,
  singleZoom,
}: {
  tickets: Ticket[];
  singleZoom: number;
}) {
  const map = useMap();

  useEffect(() => {
    if (tickets.length === 0) {
      map.setView([BEIRUT_CENTER.latitude, BEIRUT_CENTER.longitude], 12);
      return;
    }

    if (tickets.length === 1) {
      const { latitude, longitude } = tickets[0].location;
      map.setView([latitude, longitude], singleZoom);
      return;
    }

    const bounds = L.latLngBounds(
      tickets.map(
        (ticket) => [ticket.location.latitude, ticket.location.longitude] as [number, number],
      ),
    );
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  }, [map, tickets, singleZoom]);

  return null;
}

export function TicketMap({ tickets, variant = 'overview' }: TicketMapProps) {
  const isDetail = variant === 'detail';
  const singleZoom = isDetail ? 16 : 14;

  return (
    <div
      className={`ticket-map${isDetail ? ' ticket-map--detail' : ''}`}
      data-testid="ticket-map"
    >
      <MapContainer
        center={[BEIRUT_CENTER.latitude, BEIRUT_CENTER.longitude]}
        zoom={singleZoom}
        scrollWheelZoom
        className="ticket-map__canvas"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitTicketBounds tickets={tickets} singleZoom={singleZoom} />
        {tickets.map((ticket) => {
          const mapsUrl = buildGoogleMapsUrl(
            ticket.location.latitude,
            ticket.location.longitude,
          );

          return (
            <Marker
              key={ticket.ticketId}
              position={[ticket.location.latitude, ticket.location.longitude]}
            >
              <Popup>
                <div className="ticket-map__popup">
                  <p className="ticket-map__popup-id">{ticket.ticketNumber}</p>
                  <p className="ticket-map__popup-meta">
                    {formatCategory(ticket.category)} · {formatStatus(ticket.status)}
                  </p>
                  <p className="ticket-map__popup-address">{ticket.location.addressText}</p>
                  <div className="ticket-map__popup-actions">
                    {!isDetail && (
                      <Link className="ticket-map__popup-link" to={`/tickets/${ticket.ticketId}`}>
                        View ticket
                      </Link>
                    )}
                    <a
                      className="ticket-map__popup-link"
                      href={mapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open in Google Maps
                    </a>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
