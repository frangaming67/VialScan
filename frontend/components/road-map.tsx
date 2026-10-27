"use client";

import { useMemo, useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, ZoomControl, useMap } from "react-leaflet";
import type { ConditionPoint, Defect, RouteSegment } from "@/lib/types";

const COLORS: Record<string, string> = {
  high: "#e15d4f",
  medium: "#e9a23b",
  low: "#45a67b",
  unknown: "#728096",
};
const CONDITION_COLORS: Record<string, string> = {
  good: "#55a27b",
  fair: "#e4ac4c",
  poor: "#d95d50",
  not_assessable: "#9aa7a9",
};

function FitRoadToBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 1) map.fitBounds(positions, { padding: [24, 24], maxZoom: 16, animate: false });
  }, [map, positions]);
  return null;
}

export default function RoadMap({ defects, conditionPoints, routeSegments = [], selectedId, onSelect }: {
  defects: Defect[];
  conditionPoints: ConditionPoint[];
  routeSegments?: RouteSegment[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const conditionSegments = [] as { key: string; positions: [number, number][]; road_condition: string }[];
  for (let index = 1; index < conditionPoints.length; index += 1) {
    const previous = conditionPoints[index - 1];
    const current = conditionPoints[index];
    if (previous.latitude === null || previous.longitude === null || current.latitude === null || current.longitude === null) continue;
    conditionSegments.push({
      key: `${previous.frame_id}-${current.frame_id}`,
      positions: [[previous.latitude, previous.longitude], [current.latitude, current.longitude]],
      road_condition: current.road_condition,
    });
  }
  const locatedConditionPoints = conditionPoints
    .filter((item) => item.latitude !== null && item.longitude !== null)
    .map((item) => ({ ...item, position: [item.latitude as number, item.longitude as number] as [number, number] }));
  const locatedDefects = defects.filter((item) => item.latitude !== null && item.longitude !== null);
  const center: [number, number] = locatedConditionPoints[0]?.position
    ?? (locatedDefects[0] ? [locatedDefects[0].latitude as number, locatedDefects[0].longitude as number] : [-34.6038, -58.3816]);
  const displaySegments = routeSegments.length ? routeSegments : conditionSegments;
  const boundsPositions = useMemo(() => {
    const routePositions = routeSegments.flatMap((segment) => segment.positions);
    if (routePositions.length > 1) return routePositions;
    return conditionPoints.flatMap((item) => item.latitude !== null && item.longitude !== null
      ? [[item.latitude, item.longitude] as [number, number]]
      : []);
  }, [routeSegments, conditionPoints]);

  return (
    <MapContainer center={center} zoom={routeSegments.length ? 15 : 16} zoomControl={false} scrollWheelZoom className="map-canvas">
      <FitRoadToBounds positions={boundsPositions} />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ZoomControl position="bottomright" />
      {displaySegments.length ? displaySegments.map((segment, index) => (
        <Polyline
          key={"key" in segment ? segment.key : `route-${index}`}
          positions={segment.positions}
          pathOptions={{ color: CONDITION_COLORS[segment.road_condition] ?? CONDITION_COLORS.not_assessable, weight: 7, opacity: 0.88, lineCap: "round", lineJoin: "round" }}
        />
      )) : locatedDefects.length > 1 && (
        <Polyline positions={locatedDefects.map((item) => [item.latitude as number, item.longitude as number])} pathOptions={{ color: "#315d76", weight: 5, opacity: 0.7 }} />
      )}
      {locatedConditionPoints.map((item) => (
        <CircleMarker
          key={item.frame_id}
          center={item.position}
          radius={4}
          pathOptions={{ color: "#fff", weight: 1, fillColor: CONDITION_COLORS[item.road_condition] ?? CONDITION_COLORS.not_assessable, fillOpacity: 1 }}
        >
          <Popup>
            <strong>Estado: {item.road_condition.replace("_", " ")}</strong><br />
            {Math.round(item.confidence * 100)}% de confianza visual<br />
            {item.summary}
          </Popup>
        </CircleMarker>
      ))}
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
