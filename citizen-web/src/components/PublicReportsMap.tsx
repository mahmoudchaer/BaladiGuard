import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import type { PublicMapViewport } from '@/services/tickets';
import type { PublicTicketMapViewportResponse } from '@/types/ticket';
import { DEFAULT_PUBLIC_MAP_REGION } from '@/utils/publicMapClustering';

type PublicReportsMapProps = {
  data: PublicTicketMapViewportResponse | null;
  onViewportChange: (viewport: PublicMapViewport) => void;
};

function ViewportReporter({ onChange }: { onChange: (viewport: PublicMapViewport) => void }) {
  const map = useMap();
  const report = () => {
    const bounds = map.getBounds();
    onChange({
      north: bounds.getNorth(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      west: bounds.getWest(),
      zoom: map.getZoom(),
    });
  };
  useMapEvents({ moveend: report, zoomend: report });
  useEffect(() => {
    report();
    // The initial map instance is stable; onChange updates are handled by the parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);
  return null;
}

const singleIcon = L.divIcon({
  className: '',
  html: '<div style="width:14px;height:14px;border-radius:50%;background:#007A3D;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3)"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

function clusterIcon(count: number) {
  return L.divIcon({
    className: '',
    html: `<div class="cluster-bubble">${count}</div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
}

export function PublicReportsMap({ data, onViewportChange }: PublicReportsMapProps) {
  return (
    <div className="map-frame ltr-isolate" dir="ltr" data-testid="public-map">
      <MapContainer
        center={[DEFAULT_PUBLIC_MAP_REGION.latitude, DEFAULT_PUBLIC_MAP_REGION.longitude]}
        zoom={12}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ViewportReporter onChange={onViewportChange} />
        <MapFeatures data={data} />
      </MapContainer>
    </div>
  );
}

function MapFeatures({ data }: { data: PublicTicketMapViewportResponse | null }) {
  const map = useMap();
  return (
    <>
      {data?.markers.map((marker) => (
        <Marker
          key={marker.ticketNumber}
          position={[marker.latitude, marker.longitude]}
          icon={singleIcon}
        >
          <Popup>
            <Link to={`/public/${marker.ticketNumber}`}>{marker.ticketNumber}</Link>
            <div>{marker.addressText}</div>
          </Popup>
        </Marker>
      ))}
      {data?.clusters.map((cluster) => (
        <Marker
          key={cluster.id}
          position={[cluster.latitude, cluster.longitude]}
          icon={clusterIcon(cluster.count)}
          eventHandlers={{
            click: () => map.setView([cluster.latitude, cluster.longitude], map.getZoom() + 2),
          }}
        >
          <Popup>
            <strong>{cluster.count} reports nearby</strong>
            <div>Zoom in to see individual reports.</div>
          </Popup>
        </Marker>
      ))}
    </>
  );
}
