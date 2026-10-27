import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import cv2

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import DefectObservation, Detection, Frame, MediaAsset, RoadDefect, RoutePoint, ScanSession
from .analyzer import PROMPT_VERSION, analyze_image, estimate_severity
from .gps import GPSPoint, location_for_time, parse_gps
from .storage import upload_object
from .video import extract_frames

logger = logging.getLogger(__name__)


def process_session(
    session_id: UUID,
    video_path: Path | None,
    gps_path: Path | None,
    image_paths: list[Path] | None = None,
) -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        session = db.get(ScanSession, session_id)
        if session is None:
            return
        session.status = "processing"
        db.commit()

        gps_points = parse_gps(gps_path) if gps_path else []
        _save_route_points(db, session_id, gps_points)
        work_dir = settings.upload_dir / "frames" / str(session_id)
        if image_paths:
            image_assets = db.scalars(select(MediaAsset).where(
                MediaAsset.session_id == session_id, MediaAsset.media_type == "image"
            ).order_by(MediaAsset.storage_path)).all()
            if len(image_assets) != len(image_paths):
                raise RuntimeError("No coinciden las imágenes recibidas con los archivos registrados.")
            frames = []
            work_dir.mkdir(parents=True, exist_ok=True)
            for index, (image_path, asset) in enumerate(zip(image_paths, image_assets)):
                image = cv2.imread(str(image_path))
                if image is None:
                    raise ValueError(f"No se pudo leer la imagen {image_path.name}.")
                frame_path = work_dir / f"frame-{index:06d}.jpg"
                if not cv2.imwrite(str(frame_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 82]):
                    raise ValueError(f"No se pudo preparar la imagen {image_path.name}.")
                frames.append((index * settings.frame_interval_seconds, frame_path, asset))
        else:
            video_asset = db.scalar(select(MediaAsset).where(
                MediaAsset.session_id == session_id, MediaAsset.media_type == "video"
            ))
            if video_asset is None or video_path is None:
                raise RuntimeError("No se encontró el video asociado a esta sesión.")
            extracted, duration = extract_frames(video_path, work_dir, settings.frame_interval_seconds)
            video_asset.duration_seconds = duration
            frames = [(elapsed, path, video_asset) for elapsed, path in extracted]
        previous: RoadDefect | None = None
        for elapsed, frame_path, media_asset in frames:
            frame_path_in_storage = f"sessions/{session_id}/frames/{frame_path.name}"
            upload_object(frame_path_in_storage, frame_path, "image/jpeg")
            latitude, longitude, matched_point = location_for_time(
                gps_points, elapsed, settings.gps_max_gap_seconds,
                settings.gps_interpolation_max_gap_seconds,
            )
            location = from_shape(Point(longitude, latitude), srid=4326) if matched_point else None
            frame = Frame(
                media_asset_id=media_asset.id,
                elapsed_seconds=elapsed,
                storage_path=frame_path_in_storage,
                location=location,
                route_point_id=matched_point.route_point_id if matched_point else None,
                georeference_status="georeferenced" if matched_point else "unreferenced",
                metadata_json={"gps_status": "matched" if matched_point else "no_gps_match"},
            )
            db.add(frame)
            db.flush()

            result, raw_text = analyze_image(frame_path)
            if not result.get("has_defect") or result.get("type") == "none":
                db.commit()
                continue
            severity, score = estimate_severity(result)
            bbox = result.get("bbox_approx") or []
            detection = Detection(
                frame_id=frame.id,
                defect_type=result["type"],
                confidence=max(0, min(1, float(result["confidence"]))),
                description=result["description"],
                region_json={"bbox_approx": bbox} if bbox else None,
                severity_estimated=severity,
                severity_score=score,
                severity_version="heuristic-v1",
                model_name=settings.openai_model,
                prompt_version=PROMPT_VERSION,
                raw_output={"response_text": raw_text, "structured": result},
            )
            db.add(detection)
            db.flush()

            if _can_merge(previous, detection, elapsed, latitude, longitude, matched_point is not None):
                previous.last_observed_at = elapsed
                previous.confidence = max(previous.confidence, detection.confidence)
                previous.severity_score = max(previous.severity_score, score)
                if _severity_rank(severity) > _severity_rank(previous.severity_estimated):
                    previous.severity_estimated = severity
                db.add(DefectObservation(road_defect_id=previous.id, detection_id=detection.id))
            else:
                defect = RoadDefect(
                    session_id=session_id,
                    defect_type=detection.defect_type,
                    location=location,
                    severity_estimated=severity,
                    severity_score=score,
                    review_status="pending",
                    description=detection.description,
                    first_observed_at=elapsed,
                    last_observed_at=elapsed,
                    confidence=detection.confidence,
                    evidence_frame_id=frame.id,
                    is_synthetic=False,
                )
                db.add(defect)
                db.flush()
                db.add(DefectObservation(road_defect_id=defect.id, detection_id=detection.id))
                previous = defect
            db.commit()

        session.status = "completed"
        session.finished_at = datetime.now(timezone.utc)
        session.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        session = db.get(ScanSession, session_id)
        if session:
            session.status = "failed"
            session.error_message = str(exc)[:2000]
            db.commit()
        logger.exception("Error processing scan session %s", session_id)
    finally:
        db.close()
        for path in [video_path, gps_path, *(image_paths or [])]:
            if path:
                path.unlink(missing_ok=True)


def _save_route_points(db: Session, session_id: UUID, points: list[GPSPoint]) -> None:
    for item in points:
        route_point = RoutePoint(
            session_id=session_id,
            elapsed_seconds=item.elapsed_seconds,
            recorded_at=item.recorded_at,
            location=from_shape(Point(item.longitude, item.latitude), srid=4326),
            altitude_m=item.altitude_m,
            speed_mps=item.speed_mps,
            heading_deg=item.heading_deg,
        )
        db.add(route_point)
        db.flush()
        item.route_point_id = route_point.id
    db.commit()


def _can_merge(
    previous: RoadDefect | None,
    detection: Detection,
    elapsed: float,
    latitude: float | None,
    longitude: float | None,
    has_location: bool,
) -> bool:
    if previous is None or previous.defect_type != detection.defect_type:
        return False
    if elapsed - previous.last_observed_at > max(4.0, settings.frame_interval_seconds * 2.5):
        return False
    if has_location and previous.location is not None:
        from geoalchemy2.shape import to_shape
        old = to_shape(previous.location)
        dx = (old.x - longitude) * 111_320 * max(0.1, abs(math.cos(math.radians(latitude))))
        dy = (old.y - latitude) * 111_320
        return math.hypot(dx, dy) <= 35
    return not has_location and previous.location is None


def _severity_rank(value: str) -> int:
    return {"unknown": 0, "low": 1, "medium": 2, "high": 3}.get(value, 0)
