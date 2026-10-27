"use client";

import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, ZoomControl } from "react-leaflet";
import type { Defect } from "@/lib/types";

const COLORS: Record<string, string> = {
  high: "#e15d4f",
  medium: "#e9a23b",
  low: "#45a67b",
  unknown: "#728096",
};

export default function RoadMap({ defects, selectedId, onSelect }: {
  defects: Defect[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const points = defects
    .filter((item) => item.latitude !== null && item.longitude !== null)
    .map((item) => [item.latitude as number, item.longitude as number] as [number, number]);
  const center: [number, number] = points[0] ?? [-34.6038, -58.3816];

  return (
    <MapContainer center={center} zoom={16} zoomControl={false} scrollWheelZoom className="map-canvas">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ZoomControl position="bottomright" />
      {points.length > 1 && <Polyline positions={points} pathOptions={{ color: "#315d76", weight: 5, opacity: 0.7 }} />}
      {defects.map((item) => item.latitude !== null && item.longitude !== null && (
        <CircleMarker
          key={item.id}
          center={[item.latitude, item.longitude]}
          radius={selectedId === item.id ? 11 : 8}
          pathOptions={{ color: "#fff", weight: 3, fillColor: COLORS[item.severity_estimated] ?? COLORS.unknown, fillOpacity: 1 }}
          eventHandlers={{ click: () => onSelect(item.id) }}
        >
          <Popup>
            <strong>{item.defect_type}</strong><br />
            Severidad estimada: {item.severity_estimated}<br />
            {item.is_synthetic ? "Dato sintético de demostración" : item.description}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
