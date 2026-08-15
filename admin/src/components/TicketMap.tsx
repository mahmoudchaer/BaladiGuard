import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
  ZoomControl,
} from 'react-leaflet';
import L from 'leaflet';
import type { Ticket, TicketPriority, TicketStatus } from '@/types/ticket';
import type { TicketMapCluster, TicketMapMarker } from '@/types/ticketCollection';
import { formatCategory, formatPriority, formatStatus } from '@/utils/labels';
import { BEIRUT_CENTER, buildGoogleMapsUrl } from '@/utils/ticketLocation';
import 'leaflet/dist/leaflet.css';
import './TicketMap.css';

type TicketMapViewportProps = {
  markers: TicketMapMarker[];
  clusters: TicketMapCluster[];
  truncated?: boolean;
  initialBounds?: {
    north: number;
    south: number;
    east: number;
    west: number;
  } | null;
  onViewportChange?: (viewport: {
    north: number;
    south: number;
    east: number;
    west: number;
    zoom: number;
  }) => void;
};

type TicketMapProps =
  | ({
      variant?: 'overview';
      tickets?: never;
    } & TicketMapViewportProps)
  | {
      variant: 'detail';
      tickets: Ticket[];
      markers?: never;
      clusters?: never;
      truncated?: never;
      onViewportChange?: never;
    };

type MarkerColorMode = 'status' | 'urgency';

const STATUS_MARKER_COLORS: Record<TicketStatus, string> = {
  SUBMITTED: '#3d6d8f',
  UNDER_REVIEW: '#b0892c',
  ASSIGNED: '#0891b2',
  IN_PROGRESS: '#ce1126',
  RESOLVED: '#007a3d',
  CLOSED: '#7a7a7a',
};

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

const MODERN_BASEMAP_URL =
  'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
const MODERN_BASEMAP_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

function getMarkerColor(
  status: TicketStatus,
  priority: TicketPriority | null,
  mode: MarkerColorMode,
): string {
  if (mode === 'urgency') {
    return priority ? URGENCY_MARKER_COLORS[priority] : URGENCY_UNSET_COLOR;
  }
  return STATUS_MARKER_COLORS[status] ?? '#5a6472';
}

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

function FitInitialBounds({
  bounds,
}: {
  bounds: TicketMapViewportProps['initialBounds'];
}) {
  const map = useMap();
  const applied = useRef(false);

  useEffect(() => {
    if (!bounds || applied.current) {
      return;
    }
    applied.current = true;
    map.fitBounds(
      [
        [bounds.south, bounds.west],
        [bounds.north, bounds.east],
      ],
      { padding: [28, 28], maxZoom: 16 },
    );
  }, [bounds, map]);

  return null;
}

function ViewportReporter({
  onViewportChange,
}: {
  onViewportChange?: TicketMapViewportProps['onViewportChange'];
}) {
  const map = useMap();
  const report = () => {
    if (!onViewportChange) {
      return;
    }
    const bounds = map.getBounds();
    onViewportChange({
      north: bounds.getNorth(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      west: bounds.getWest(),
      zoom: map.getZoom(),
    });
  };

  useMapEvents({
    moveend: report,
    zoomend: report,
  });

  useEffect(() => {
    report();
    // Initial viewport once the map instance is ready.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  return null;
}

function ClusterMarker({ cluster }: { cluster: TicketMapCluster }) {
  const map = useMap();
  return (
    <CircleMarker
      center={[cluster.latitude, cluster.longitude]}
      radius={Math.min(28, 10 + Math.log2(cluster.count + 1) * 4)}
      pathOptions={{
        color: '#0f4c81',
        fillColor: '#1d6fb8',
        fillOpacity: 0.72,
        weight: 2,
      }}
      eventHandlers={{
        click: () => {
          map.setView([cluster.latitude, cluster.longitude], Math.min(18, map.getZoom() + 2));
        },
      }}
    >
      <Popup>
        <div className="ticket-map__popup">
          <p className="ticket-map__popup-id">{cluster.count} reports</p>
          <p className="ticket-map__popup-meta">Zoom in to see individual tickets</p>
        </div>
      </Popup>
    </CircleMarker>
  );
}

function DetailTicketMap({ tickets }: { tickets: Ticket[] }) {
  const singleZoom = 16;
  const [colorMode] = useState<MarkerColorMode>('status');

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
    <div className="ticket-map ticket-map--detail" data-testid="ticket-map">
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
          const color = getMarkerColor(ticket.status, ticket.priority, colorMode);

          return (
            <Marker
              key={ticket.ticketId}
              position={[ticket.location.latitude, ticket.location.longitude]}
              icon={buildMarkerIcon(color, false)}
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

function OverviewTicketMap({
  markers,
  clusters,
  truncated = false,
  initialBounds = null,
  onViewportChange,
}: TicketMapViewportProps) {
  const [colorMode, setColorMode] = useState<MarkerColorMode>('status');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);

  const legendItems = useMemo(() => {
    if (colorMode === 'urgency') {
      return URGENCY_LEGEND_ORDER.map((priority) => ({
        key: priority,
        label: formatPriority(priority),
        color: URGENCY_MARKER_COLORS[priority],
        count: markers.filter((marker) => marker.priority === priority).length,
      }));
    }

    return STATUS_LEGEND_ORDER.map((status) => ({
      key: status,
      label: formatStatus(status),
      color: STATUS_MARKER_COLORS[status],
      count: markers.filter((marker) => marker.status === status).length,
    }));
  }, [colorMode, markers]);

  const hasContent = markers.length > 0 || clusters.length > 0;

  return (
    <div className="ticket-map" data-testid="ticket-map">
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
        {truncated ? (
          <p className="ticket-map__truncated" role="status">
            Showing a bounded sample for this viewport
          </p>
        ) : null}
      </div>

      <MapContainer
        center={[BEIRUT_CENTER.latitude, BEIRUT_CENTER.longitude]}
        zoom={12}
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
        <FitInitialBounds bounds={initialBounds} />
        <ViewportReporter onViewportChange={onViewportChange} />
        {clusters.map((cluster) => (
          <ClusterMarker key={cluster.id} cluster={cluster} />
        ))}
        {markers.map((marker) => {
          const mapsUrl = buildGoogleMapsUrl(marker.latitude, marker.longitude);
          const color = getMarkerColor(marker.status, marker.priority, colorMode);
          const selected = marker.ticketId === selectedTicketId;
          const label = marker.ticketNumber ?? marker.ticketId;

          return (
            <Marker
              key={marker.ticketId}
              position={[marker.latitude, marker.longitude]}
              icon={buildMarkerIcon(color, selected)}
              eventHandlers={{
                click: () => setSelectedTicketId(marker.ticketId),
                popupclose: () =>
                  setSelectedTicketId((current) => (current === marker.ticketId ? null : current)),
              }}
            >
              <Popup className="ticket-map__popup-shell" maxWidth={280}>
                <div className="ticket-map__popup">
                  <p className="ticket-map__popup-id">{label}</p>
                  <p className="ticket-map__popup-meta">
                    {formatCategory(marker.category)} · {formatStatus(marker.status)}
                    {marker.priority ? ` · ${formatPriority(marker.priority)} urgency` : ''}
                  </p>
                  <div className="ticket-map__popup-actions">
                    <Link className="ticket-map__popup-link" to={`/tickets/${marker.ticketId}`}>
                      View ticket
                    </Link>
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

      {!hasContent && (
        <p className="ticket-map__empty-overlay" role="status">
          Pan or zoom to load reports in this area.
        </p>
      )}
    </div>
  );
}

export function TicketMap(props: TicketMapProps) {
  if (props.variant === 'detail') {
    return <DetailTicketMap tickets={props.tickets} />;
  }

  return (
    <OverviewTicketMap
      markers={props.markers}
      clusters={props.clusters}
      truncated={props.truncated}
      initialBounds={props.initialBounds}
      onViewportChange={props.onViewportChange}
    />
  );
}
