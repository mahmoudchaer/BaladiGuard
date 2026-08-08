import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer, useMap, ZoomControl } from 'react-leaflet';
import L from 'leaflet';
import type { Ticket, TicketPriority, TicketStatus } from '@/types/ticket';
import { formatCategory, formatPriority, formatStatus } from '@/utils/labels';
import { BEIRUT_CENTER, buildGoogleMapsUrl } from '@/utils/ticketLocation';
import 'leaflet/dist/leaflet.css';
import './TicketMap.css';

type TicketMapProps = {
  tickets: Ticket[];
  /** Compact map for ticket detail; overview is the full Map View. */
  variant?: 'overview' | 'detail';
};

type MarkerColorMode = 'status' | 'urgency';

/** Mirrors the --status-*-dot tokens in index.css so map pins match badge colors. */
const STATUS_MARKER_COLORS: Record<TicketStatus, string> = {
  SUBMITTED: '#3d6d8f',
  UNDER_REVIEW: '#b0892c',
  ASSIGNED: '#0891b2',
  IN_PROGRESS: '#ce1126',
  RESOLVED: '#007a3d',
  CLOSED: '#7a7a7a',
};

/** Mirrors the --urgency-*-fg tokens in index.css. */
const URGENCY_MARKER_COLORS: Record<TicketPriority, string> = {
  low: '#4f5d6f',
  medium: '#8f4a08',
  high: '#a50e1f',
  critical: '#6d121d',
};

const URGENCY_UNSET_COLOR = '#94a3b8';

const STATUS_LEGEND_ORDER: TicketStatus[] = [
  'SUBMITTED',
  'UNDER_REVIEW',
  'ASSIGNED',
  'IN_PROGRESS',
  'RESOLVED',
  'CLOSED',
];

const URGENCY_LEGEND_ORDER: TicketPriority[] = ['critical', 'high', 'medium', 'low'];

/**
 * CARTO Voyager — free, modern Google/Apple-like basemap (soft roads, clean parks).
 * Retina tiles via {r}.
 */
const MODERN_BASEMAP_URL =
  'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
const MODERN_BASEMAP_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

function getMarkerColor(ticket: Ticket, mode: MarkerColorMode): string {
  if (mode === 'urgency') {
    return ticket.priority ? URGENCY_MARKER_COLORS[ticket.priority] : URGENCY_UNSET_COLOR;
  }
  return STATUS_MARKER_COLORS[ticket.status] ?? '#5a6472';
}

/** Google/Apple-style teardrop pin instead of a flat OSM circle. */
function buildMarkerIcon(color: string, selected: boolean): L.DivIcon {
  const width = selected ? 34 : 28;
  const height = selected ? 44 : 36;
  const selectedClass = selected ? ' ticket-map__pin--selected' : '';

  return L.divIcon({
    className: 'ticket-map__marker',
    html: `
      <span class="ticket-map__pin${selectedClass}" style="--pin-color:${color}">
        <svg viewBox="0 0 28 36" width="${width}" height="${height}" aria-hidden="true">
          <path
            fill="${color}"
            d="M14 1.2C7.6 1.2 2.4 6.4 2.4 12.8c0 8.2 9.4 19.6 11 21.4a.8.8 0 0 0 1.2 0c1.6-1.8 11-13.2 11-21.4C25.6 6.4 20.4 1.2 14 1.2z"
          />
          <circle cx="14" cy="12.8" r="4.4" fill="#fff"/>
        </svg>
      </span>
    `,
    iconSize: [width, height],
    iconAnchor: [width / 2, height - 2],
    popupAnchor: [0, -(height - 6)],
  });
}

function FitTicketBounds({ tickets, singleZoom }: { tickets: Ticket[]; singleZoom: number }) {
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
    map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15 });
  }, [map, tickets, singleZoom]);

  return null;
}

export function TicketMap({ tickets, variant = 'overview' }: TicketMapProps) {
  const isDetail = variant === 'detail';
  const singleZoom = isDetail ? 16 : 14;
  const [colorMode, setColorMode] = useState<MarkerColorMode>('status');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);

  const legendItems = useMemo(() => {
    if (colorMode === 'urgency') {
      return URGENCY_LEGEND_ORDER.map((priority) => ({
        key: priority,
        label: formatPriority(priority),
        color: URGENCY_MARKER_COLORS[priority],
        count: tickets.filter((ticket) => ticket.priority === priority).length,
      }));
    }

    return STATUS_LEGEND_ORDER.map((status) => ({
      key: status,
      label: formatStatus(status),
      color: STATUS_MARKER_COLORS[status],
      count: tickets.filter((ticket) => ticket.status === status).length,
    }));
  }, [colorMode, tickets]);

  if (tickets.length === 0) {
    return (
      <div className="ticket-map ticket-map--empty" data-testid="ticket-map">
        <p className="ticket-map__empty-message">
          No tickets with map coordinates to display right now.
        </p>
      </div>
    );
  }

  return (
    <div className={`ticket-map${isDetail ? ' ticket-map--detail' : ''}`} data-testid="ticket-map">
      {!isDetail && (
        <div className="ticket-map__legend" aria-label="Map legend">
          <p className="ticket-map__legend-title">Map layers</p>
          <div className="ticket-map__legend-toggle" role="group" aria-label="Color pins by">
            <button
              type="button"
              className={`ticket-map__legend-toggle-btn${
                colorMode === 'status' ? ' ticket-map__legend-toggle-btn--active' : ''
              }`}
              aria-pressed={colorMode === 'status'}
              onClick={() => setColorMode('status')}
            >
              Status
            </button>
            <button
              type="button"
              className={`ticket-map__legend-toggle-btn${
                colorMode === 'urgency' ? ' ticket-map__legend-toggle-btn--active' : ''
              }`}
              aria-pressed={colorMode === 'urgency'}
              onClick={() => setColorMode('urgency')}
            >
              Urgency
            </button>
          </div>
          <ul className="ticket-map__legend-list">
            {legendItems.map((item) => (
              <li key={item.key} className="ticket-map__legend-item">
                <span
                  className="ticket-map__legend-dot"
                  style={{ background: item.color }}
                  aria-hidden="true"
                />
                <span className="ticket-map__legend-label">{item.label}</span>
                <span className="ticket-map__legend-count">{item.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <MapContainer
        center={[BEIRUT_CENTER.latitude, BEIRUT_CENTER.longitude]}
        zoom={singleZoom}
        scrollWheelZoom
        zoomControl={false}
        className="ticket-map__canvas"
      >
        <TileLayer
          attribution={MODERN_BASEMAP_ATTR}
          url={MODERN_BASEMAP_URL}
          maxZoom={20}
          subdomains="abcd"
        />
        <ZoomControl position="bottomright" />
        <FitTicketBounds tickets={tickets} singleZoom={singleZoom} />
        {tickets.map((ticket) => {
          const mapsUrl = buildGoogleMapsUrl(ticket.location.latitude, ticket.location.longitude);
          const color = getMarkerColor(ticket, colorMode);
          const selected = !isDetail && ticket.ticketId === selectedTicketId;

          return (
            <Marker
              key={ticket.ticketId}
              position={[ticket.location.latitude, ticket.location.longitude]}
              icon={buildMarkerIcon(color, selected)}
              eventHandlers={
                isDetail
                  ? undefined
                  : {
                      click: () => setSelectedTicketId(ticket.ticketId),
                      popupclose: () =>
                        setSelectedTicketId((current) =>
                          current === ticket.ticketId ? null : current,
                        ),
                    }
              }
            >
              <Popup className="ticket-map__popup-shell" maxWidth={280}>
                <div className="ticket-map__popup">
                  <p className="ticket-map__popup-id">{ticket.ticketNumber}</p>
                  <p className="ticket-map__popup-meta">
                    {formatCategory(ticket.category)} · {formatStatus(ticket.status)}
                    {ticket.priority ? ` · ${formatPriority(ticket.priority)} urgency` : ''}
                  </p>
                  <p className="ticket-map__popup-address">{ticket.location.addressText}</p>
                  <div className="ticket-map__popup-actions">
                    {!isDetail && (
                      <Link className="ticket-map__popup-link" to={`/tickets/${ticket.ticketId}`}>
                        View ticket
                      </Link>
                    )}
                    <a
                      className="ticket-map__popup-link ticket-map__popup-link--secondary"
                      href={mapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open in Maps
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
