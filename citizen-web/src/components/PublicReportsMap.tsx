import { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { PublicTicketResponse } from '@/types/ticket';
import {
  DEFAULT_PUBLIC_MAP_REGION,
  clusterPublicReports,
  initialRegionForPlottable,
  partitionPlottableReports,
  type PublicMapFeature,
} from '@/utils/publicMapClustering';

type PublicReportsMapProps = {
  reports: PublicTicketResponse[];
};

function FitBounds({ features }: { features: PublicMapFeature[] }) {
  const map = useMap();
  useEffect(() => {
    if (features.length === 0) {
      map.setView([DEFAULT_PUBLIC_MAP_REGION.latitude, DEFAULT_PUBLIC_MAP_REGION.longitude], 12);
      return;
    }
    const bounds = L.latLngBounds(
      features.map((feature) => [feature.latitude, feature.longitude] as [number, number]),
    );
    map.fitBounds(bounds.pad(0.2));
  }, [features, map]);
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

export function PublicReportsMap({ reports }: PublicReportsMapProps) {
  const { plottable } = useMemo(() => partitionPlottableReports(reports), [reports]);
  const region = useMemo(() => initialRegionForPlottable(plottable), [plottable]);
  const features = useMemo(() => clusterPublicReports(plottable, region), [plottable, region]);

  return (
    <div className="map-frame" data-testid="public-map">
      <MapContainer
        center={[region.latitude, region.longitude]}
        zoom={13}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds features={features} />
        {features.map((feature) =>
          feature.kind === 'single' ? (
            <Marker
              key={feature.id}
              position={[feature.latitude, feature.longitude]}
              icon={singleIcon}
            >
              <Popup>
                <Link to={`/public/${feature.report.ticketNumber}`}>
                  {feature.report.ticketNumber}
                </Link>
                <div>{feature.report.location.addressText}</div>
              </Popup>
            </Marker>
          ) : (
            <Marker
              key={feature.id}
              position={[feature.latitude, feature.longitude]}
              icon={clusterIcon(feature.count)}
            >
              <Popup>
                <strong>{feature.count} reports nearby</strong>
                <ul>
                  {feature.reports.slice(0, 8).map((report) => (
                    <li key={report.ticketNumber}>
                      <Link to={`/public/${report.ticketNumber}`}>{report.ticketNumber}</Link>
                    </li>
                  ))}
                </ul>
              </Popup>
            </Marker>
          ),
        )}
      </MapContainer>
    </div>
  );
}
