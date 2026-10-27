import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID
from xml.etree import ElementTree


@dataclass
class GPSPoint:
    elapsed_seconds: float
    latitude: float
    longitude: float
    altitude_m: float | None = None
    speed_mps: float | None = None
    heading_deg: float | None = None
    route_point_id: UUID | None = None
    recorded_at: datetime | None = None


def parse_gps(path: Path) -> list[GPSPoint]:
    if path.suffix.lower() == ".gpx":
        return _parse_gpx(path)
    if path.suffix.lower() == ".csv":
        return _parse_csv(path)
    raise ValueError("El archivo GPS debe ser GPX o CSV.")


def _parse_gpx(path: Path) -> list[GPSPoint]:
    root = ElementTree.parse(path).getroot()
    timed_points: list[tuple[datetime, float, float, float | None]] = []
    for node in root.iter():
        if not node.tag.endswith(("trkpt", "rtept")):
            continue
        stamp = None
        altitude = None
        for child in node:
            if child.tag.endswith("time") and child.text:
                stamp = datetime.fromisoformat(child.text.replace("Z", "+00:00"))
            elif child.tag.endswith("ele") and child.text:
                altitude = float(child.text)
        if stamp:
            timed_points.append((stamp, float(node.attrib["lat"]), float(node.attrib["lon"]), altitude))
    if not timed_points:
        raise ValueError("El GPX no tiene puntos con hora; usa un GPX con timestamps o un CSV.")
    start = timed_points[0][0]
    return [GPSPoint((stamp - start).total_seconds(), lat, lon, altitude, recorded_at=stamp)
            for stamp, lat, lon, altitude in timed_points]


def _parse_csv(path: Path) -> list[GPSPoint]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("El CSV GPS necesita encabezados.")
        names = {name.strip().lower(): name for name in reader.fieldnames}

        def field(row: dict, *candidates: str) -> str | None:
            for key in candidates:
                original = names.get(key)
                if original and row.get(original):
                    return row[original]
            return None

        rows = []
        for row in reader:
            lat = field(row, "latitude", "lat")
            lon = field(row, "longitude", "lon", "lng")
            elapsed = field(row, "elapsed_seconds", "seconds", "time_seconds")
            stamp = field(row, "timestamp", "time")
            if lat is not None and lon is not None:
                rows.append((row, float(lat), float(lon), float(elapsed) if elapsed else None, stamp))
    if not rows:
        raise ValueError("El CSV no contiene puntos latitude/longitude.")

    parsed_stamps = [datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None
                     for _, _, _, _, stamp in rows]
    first_stamp = next((stamp for stamp in parsed_stamps if stamp is not None), None)
    points = []
    for (row, lat, lon, elapsed, _), stamp in zip(rows, parsed_stamps):
        if elapsed is None:
            if stamp is None or first_stamp is None:
                raise ValueError("Usa elapsed_seconds o una columna timestamp/time en el CSV.")
            elapsed = (stamp - first_stamp).total_seconds()
        names = {name.strip().lower(): name for name in row}

        def optional(*keys: str) -> float | None:
            value = next((row[names[key]] for key in keys if names.get(key) and row.get(names[key])), None)
            return float(value) if value else None

        points.append(GPSPoint(
            max(0, elapsed), lat, lon,
            optional("altitude", "altitude_m", "elevation"),
            optional("speed", "speed_mps"),
            optional("heading", "heading_deg", "course"),
            recorded_at=stamp,
        ))
    return sorted(points, key=lambda item: item.elapsed_seconds)


def location_for_time(
    points: list[GPSPoint], elapsed: float, tolerance: float, interpolation_gap: float,
) -> tuple[float | None, float | None, GPSPoint | None]:
    if not points:
        return None, None, None
    before = next((point for point in reversed(points) if point.elapsed_seconds <= elapsed), None)
    after = next((point for point in points if point.elapsed_seconds >= elapsed), None)
    if before and after and before is not after:
        gap = after.elapsed_seconds - before.elapsed_seconds
        if 0 < gap <= interpolation_gap:
            ratio = (elapsed - before.elapsed_seconds) / gap
            nearest = before if ratio <= 0.5 else after
            return (
                before.latitude + (after.latitude - before.latitude) * ratio,
                before.longitude + (after.longitude - before.longitude) * ratio,
                nearest,
            )
    nearest = min(points, key=lambda point: abs(point.elapsed_seconds - elapsed))
    if abs(nearest.elapsed_seconds - elapsed) <= tolerance:
        return nearest.latitude, nearest.longitude, nearest
    return None, None, None
