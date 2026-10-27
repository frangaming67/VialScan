import asyncio
import hashlib
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db
from .demo import DEMO
from .models import Frame, MediaAsset, RoadDefect, ScanSession
from .schemas import ConditionPointOut, DefectOut, DefectUpdate, SessionCreate, SessionOut, SessionUploadOut
from .services.processor import process_session
from .services.storage import signed_url, upload_object
from .services.local_analyzer import analyze_local_image
from .services.gps import GPSPoint, location_for_time, parse_gps
from .services.video import extract_frames, video_duration

logging.basicConfig(level=logging.INFO)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".webm", ".m4v"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GPS_SUFFIXES = {".gpx", ".csv"}


def _require_ready_for_upload() -> None:
    missing = []
    if not settings.database_ready:
        missing.append("DATABASE_URL")
    if not settings.storage_ready:
        missing.extend(["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET"])
    if not settings.analysis_ready:
        missing.extend(["OPENAI_API_KEY", "OPENAI_MODEL"])
    if missing:
        unique = list(dict.fromkeys(missing))
        raise HTTPException(
            status_code=503,
            detail=f"Faltan variables para procesar recorridos reales: {', '.join(unique)}. Usa el modo de demostración mientras tanto.",
        )


def _defect_out(db: Session, defect: RoadDefect) -> DefectOut:
    latitude = longitude = None
    if defect.location is not None:
        point = to_shape(defect.location)
        longitude, latitude = point.x, point.y
    frame = db.get(Frame, defect.evidence_frame_id)
    evidence_url = signed_url(frame.storage_path) if frame else None
    return DefectOut(
        id=defect.id,
        session_id=defect.session_id,
        defect_type=defect.defect_type,
        severity_estimated=defect.severity_estimated,
        severity_score=defect.severity_score,
        review_status=defect.review_status,
        description=defect.description,
        first_observed_at=defect.first_observed_at,
        last_observed_at=defect.last_observed_at,
        confidence=defect.confidence,
        latitude=latitude,
        longitude=longitude,
        evidence_url=evidence_url,
        is_synthetic=defect.is_synthetic,
    )


def _session_out(db: Session, session: ScanSession) -> SessionOut:
    defects = db.scalars(select(RoadDefect).where(RoadDefect.session_id == session.id).order_by(RoadDefect.first_observed_at)).all()
    frames = db.scalars(
        select(Frame)
        .join(MediaAsset, Frame.media_asset_id == MediaAsset.id)
        .where(MediaAsset.session_id == session.id)
        .order_by(Frame.elapsed_seconds)
    ).all()
    condition_points = []
    for frame in frames:
        latitude = longitude = None
        if frame.location is not None:
            point = to_shape(frame.location)
            longitude, latitude = point.x, point.y
        metadata = frame.metadata_json or {}
        condition_points.append(ConditionPointOut(
            frame_id=frame.id,
            elapsed_seconds=frame.elapsed_seconds,
            road_condition=metadata.get("road_condition", "not_assessable"),
            confidence=metadata.get("frame_confidence", 0),
            summary=metadata.get("condition_summary", ""),
            latitude=latitude,
            longitude=longitude,
        ))
    return SessionOut(
        id=session.id, name=session.name, status=session.status, started_at=session.started_at,
        finished_at=session.finished_at, error_message=session.error_message,
        analysis_summary=(session.metadata_json or {}).get("analysis_summary", {}),
        condition_points=condition_points,
        defects=[_defect_out(db, defect) for defect in defects],
    )


async def _save_upload(upload: UploadFile, destination: Path, limit_bytes: int) -> int:
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="El archivo supera el límite permitido.")
            out.write(chunk)
    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    return size


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/config")
def config_status() -> dict:
    missing = []
    if not settings.database_ready:
        missing.append("DATABASE_URL")
    if not settings.storage_ready:
        missing.extend(["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_STORAGE_BUCKET"])
    if not settings.analysis_ready:
        missing.extend(["OPENAI_API_KEY", "OPENAI_MODEL"])
    return {
        "real_processing_ready": not missing,
        "local_processing_ready": True,
        "missing_variables": list(dict.fromkeys(missing)),
        "frame_interval_seconds": settings.frame_interval_seconds,
        "model": settings.openai_model if settings.analysis_ready else None,
    }


@app.get("/api/demo")
def demo_data() -> dict:
    return DEMO


def _local_analysis_result(name: str, frames: list[dict], gps_points: list[GPSPoint]) -> dict:
    session_id = uuid4()
    started_at = datetime.now(timezone.utc)
    defects = []
    condition_points = []
    image_results = []
    category_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    condition_counts = {"good": 0, "fair": 0, "poor": 0, "not_assessable": 0}

    for frame in frames:
        frame_id = uuid4()
        elapsed_seconds = frame["elapsed_seconds"]
        result = frame["result"]
        condition = result["road_condition"]
        latitude, longitude, matched_point = location_for_time(
            gps_points, elapsed_seconds, settings.gps_max_gap_seconds,
            settings.gps_interpolation_max_gap_seconds,
        )
        detections = result["detections"]
        condition_counts[condition] += 1
        condition_points.append({
            "frame_id": str(frame_id),
            "elapsed_seconds": elapsed_seconds,
            "road_condition": condition,
            "confidence": result["frame_confidence"],
            "summary": result["summary"],
            "latitude": latitude if matched_point else None,
            "longitude": longitude if matched_point else None,
            "is_synthetic": False,
        })
        image_results.append({
            "frame_id": str(frame_id),
            "file_name": frame["file_name"],
            "evidence_url": result["evidence_url"],
            "road_condition": condition,
            "confidence": result["frame_confidence"],
            "summary": result["summary"],
            "defect_count": len(detections),
        })

        for detection in detections:
            defect_type = detection["defect_type"]
            severity = detection["severity_estimated"]
            category_counts[defect_type] = category_counts.get(defect_type, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            defects.append({
                "id": str(uuid4()),
                "session_id": str(session_id),
                "frame_id": str(frame_id),
                "defect_type": defect_type,
                "severity_estimated": severity,
                "severity_score": detection["severity_score"],
                "bbox_approx": detection["bbox_approx"],
                "review_status": "pending",
                "description": f"{frame['file_name']}: {detection['description']}",
                "first_observed_at": elapsed_seconds,
                "last_observed_at": elapsed_seconds,
                "confidence": detection["confidence"],
                "latitude": latitude if matched_point else None,
                "longitude": longitude if matched_point else None,
                "evidence_url": None,
                "is_synthetic": False,
                "is_local": True,
            })

    if len(gps_points) > 1:
        stride = max(1, (len(gps_points) + 1499) // 1500)
        route = gps_points[::stride]
        if route[-1] is not gps_points[-1]:
            route.append(gps_points[-1])
        route_segments = [{
            "road_condition": "not_assessable",
            "positions": [[point.latitude, point.longitude] for point in route],
        }]
    else:
        route_segments = []

    frames_total = len(frames)
    finished_at = datetime.now(timezone.utc)
    return {
        "id": str(session_id),
        "name": name.strip() or "Recorrido local",
        "status": "completed",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "error_message": None,
        "is_local": True,
        "analysis_summary": {
            "frames_total": frames_total,
            "condition_counts": condition_counts,
            "condition_percentages": {key: round(value * 100 / frames_total, 1) for key, value in condition_counts.items()},
            "defect_observations": len(defects),
            "consolidated_incidents": len(defects),
            "category_counts": category_counts,
            "severity_counts": severity_counts,
        },
        "route_segments": route_segments,
        "condition_points": condition_points,
        "image_results": image_results,
        "defects": defects,
    }


async def _load_local_gps(gps: UploadFile | None, directory: Path) -> list[GPSPoint]:
    if not gps:
        return []
    suffix = Path(gps.filename or "").suffix.lower()
    if suffix not in GPS_SUFFIXES:
        raise HTTPException(status_code=415, detail="El archivo GPS debe ser GPX o CSV.")
    path = directory / f"route{suffix}"
    await _save_upload(gps, path, 10 * 1024 * 1024)
    try:
        return parse_gps(path)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el track GPS: {error}") from error


@app.post("/api/local-analysis/images")
async def analyze_images_locally(
    images: Annotated[list[UploadFile] | None, File()] = None,
    gps: Annotated[UploadFile | None, File()] = None,
    name: Annotated[str, Form()] = "Secuencia de imágenes",
) -> dict:
    if not images or len(images) > 30:
        raise HTTPException(status_code=400, detail="Carga entre 1 y 30 imágenes.")
    if any(Path(item.filename or "").suffix.lower() not in IMAGE_SUFFIXES for item in images):
        raise HTTPException(status_code=415, detail="Usa imágenes JPG, PNG o WEBP.")

    frames = []
    total_image_bytes = 0
    with tempfile.TemporaryDirectory(prefix="vialscan-local-") as temporary:
        gps_points = await _load_local_gps(gps, Path(temporary))
        for index, upload in enumerate(images):
            image_bytes = await upload.read(12 * 1024 * 1024 + 1)
            if len(image_bytes) > 12 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"{upload.filename or 'Una imagen'} supera el límite de 12 MB.")
            total_image_bytes += len(image_bytes)
            if total_image_bytes > 30 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="La secuencia completa supera el límite de 30 MB.")
            if not image_bytes:
                raise HTTPException(status_code=400, detail=f"{upload.filename or 'Una imagen'} está vacía.")
            try:
                result = await asyncio.to_thread(analyze_local_image, image_bytes)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            except RuntimeError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
            frames.append({
                "file_name": Path(upload.filename or f"foto-{index + 1}.jpg").name,
                "elapsed_seconds": index * settings.frame_interval_seconds,
                "result": result,
            })
    return _local_analysis_result(name, frames, gps_points)


@app.post("/api/local-analysis/video")
async def analyze_video_locally(
    video: Annotated[UploadFile, File()],
    gps: Annotated[UploadFile | None, File()] = None,
    name: Annotated[str, Form()] = "Video de recorrido",
) -> dict:
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        raise HTTPException(status_code=415, detail="Usa un video MP4, MOV, AVI, WEBM o M4V.")

    with tempfile.TemporaryDirectory(prefix="vialscan-video-") as temporary:
        directory = Path(temporary)
        video_path = directory / f"source{suffix}"
        await _save_upload(video, video_path, settings.max_video_mb * 1024 * 1024)
        gps_points = await _load_local_gps(gps, directory)
        try:
            duration = await asyncio.to_thread(video_duration, video_path)
            if duration > 180:
                raise HTTPException(status_code=413, detail="Para análisis local, el video debe durar 3 minutos o menos.")
            extracted, _ = await asyncio.to_thread(
                extract_frames, video_path, directory / "frames", settings.frame_interval_seconds,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        frames = []
        for elapsed, frame_path in extracted:
            try:
                result = await asyncio.to_thread(analyze_local_image, frame_path.read_bytes())
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            except RuntimeError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
            frames.append({
                "file_name": f"{Path(video.filename or 'video').name} · {int(elapsed // 60):02d}:{int(elapsed % 60):02d}",
                "elapsed_seconds": elapsed,
                "result": result,
            })
    return _local_analysis_result(name, frames, gps_points)


@app.post("/api/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)) -> SessionOut:
    if not settings.database_ready:
        raise HTTPException(status_code=503, detail="Configura DATABASE_URL para guardar sesiones reales.")
    session = ScanSession(name=payload.name.strip(), status="created", started_at=datetime.now(timezone.utc))
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(db, session)


@app.get("/api/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)) -> list[SessionOut]:
    sessions = db.scalars(select(ScanSession).order_by(ScanSession.created_at.desc()).limit(50)).all()
    return [_session_out(db, session) for session in sessions]


@app.get("/api/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionOut:
    session = db.get(ScanSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="No se encontró la sesión.")
    return _session_out(db, session)


@app.post("/api/sessions/{session_id}/upload", response_model=SessionUploadOut, status_code=202)
async def upload_session_media(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    video: Annotated[UploadFile, File()],
    gps: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
) -> SessionUploadOut:
    _require_ready_for_upload()
    session = db.get(ScanSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="No se encontró la sesión.")
    if session.status != "created":
        raise HTTPException(status_code=409, detail="Esta sesión ya tiene archivos o está en procesamiento. Crea otra sesión para un nuevo recorrido.")
    video_suffix = Path(video.filename or "video.mp4").suffix.lower()
    if video_suffix not in VIDEO_SUFFIXES:
        raise HTTPException(status_code=415, detail="Formato de video no admitido. Usa MP4, MOV, AVI, WEBM o M4V.")
    gps_suffix = Path(gps.filename or "").suffix.lower() if gps else None
    if gps and gps_suffix not in GPS_SUFFIXES:
        raise HTTPException(status_code=415, detail="El archivo GPS debe ser GPX o CSV.")

    temp_dir = settings.upload_dir / "incoming" / str(session_id)
    video_path = temp_dir / f"source{video_suffix}"
    gps_path = temp_dir / f"route{gps_suffix}" if gps and gps_suffix else None
    try:
        video_size = await _save_upload(video, video_path, settings.max_video_mb * 1024 * 1024)
        video_storage_path = f"sessions/{session_id}/source{video_suffix}"
        upload_object(video_storage_path, video_path, video.content_type or "video/mp4")
        db.add(MediaAsset(
            session_id=session_id, media_type="video", storage_path=video_storage_path,
            sha256=_sha256(video_path), size_bytes=video_size,
            metadata_json={"filename": Path(video.filename or "video").name},
        ))
        if gps and gps_path:
            gps_size = await _save_upload(gps, gps_path, 10 * 1024 * 1024)
            gps_storage_path = f"sessions/{session_id}/route{gps_suffix}"
            upload_object(gps_storage_path, gps_path, "text/csv" if gps_suffix == ".csv" else "application/gpx+xml")
            db.add(MediaAsset(
                session_id=session_id, media_type="gps", storage_path=gps_storage_path,
                sha256=_sha256(gps_path), size_bytes=gps_size,
                metadata_json={"filename": Path(gps.filename or "route").name},
            ))
        session.status = "queued"
        session.error_message = None
        db.commit()
    except HTTPException:
        db.rollback()
        video_path.unlink(missing_ok=True)
        if gps_path:
            gps_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        db.rollback()
        video_path.unlink(missing_ok=True)
        if gps_path:
            gps_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"No se pudo guardar el archivo: {str(exc)[:300]}") from exc

    background_tasks.add_task(process_session, session_id, video_path, gps_path)
    return SessionUploadOut(id=session_id, status="queued", message="Video recibido; el análisis se procesa en segundo plano.")


@app.post("/api/sessions/{session_id}/images", response_model=SessionUploadOut, status_code=202)
async def upload_session_images(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    images: Annotated[list[UploadFile], File()],
    gps: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
) -> SessionUploadOut:
    _require_ready_for_upload()
    session = db.get(ScanSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="No se encontró la sesión.")
    if session.status != "created":
        raise HTTPException(status_code=409, detail="Esta sesión ya tiene archivos o está en procesamiento. Crea otra sesión para un nuevo recorrido.")
    if not images or len(images) > 30:
        raise HTTPException(status_code=400, detail="Carga entre 1 y 30 imágenes por recorrido.")
    if any(Path(item.filename or "").suffix.lower() not in IMAGE_SUFFIXES for item in images):
        raise HTTPException(status_code=415, detail="Formato de imagen no admitido. Usa JPG, PNG o WEBP.")
    gps_suffix = Path(gps.filename or "").suffix.lower() if gps else None
    if gps and gps_suffix not in GPS_SUFFIXES:
        raise HTTPException(status_code=415, detail="El archivo GPS debe ser GPX o CSV.")

    temp_dir = settings.upload_dir / "incoming" / str(session_id)
    image_paths: list[Path] = []
    gps_path = temp_dir / f"route{gps_suffix}" if gps and gps_suffix else None
    try:
        total_size = 0
        for index, image in enumerate(images):
            suffix = Path(image.filename or "image.jpg").suffix.lower()
            image_path = temp_dir / f"image-{index:03d}{suffix}"
            image_size = await _save_upload(image, image_path, 12 * 1024 * 1024)
            total_size += image_size
            if total_size > settings.max_video_mb * 1024 * 1024:
                raise HTTPException(status_code=413, detail="El conjunto de imágenes supera el límite permitido.")
            storage_path = f"sessions/{session_id}/images/{index:03d}{suffix}"
            upload_object(storage_path, image_path, image.content_type or "image/jpeg")
            db.add(MediaAsset(
                session_id=session_id, media_type="image", storage_path=storage_path,
                sha256=_sha256(image_path), size_bytes=image_size,
                metadata_json={"filename": Path(image.filename or "image").name, "sequence_index": index},
            ))
            image_paths.append(image_path)
        if gps and gps_path:
            gps_size = await _save_upload(gps, gps_path, 10 * 1024 * 1024)
            gps_storage_path = f"sessions/{session_id}/route{gps_suffix}"
            upload_object(gps_storage_path, gps_path, "text/csv" if gps_suffix == ".csv" else "application/gpx+xml")
            db.add(MediaAsset(
                session_id=session_id, media_type="gps", storage_path=gps_storage_path,
                sha256=_sha256(gps_path), size_bytes=gps_size,
                metadata_json={"filename": Path(gps.filename or "route").name},
            ))
        session.status = "queued"
        session.error_message = None
        db.commit()
    except HTTPException:
        db.rollback()
        for path in [*image_paths, gps_path]:
            if path:
                path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        db.rollback()
        for path in [*image_paths, gps_path]:
            if path:
                path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"No se pudieron guardar las imágenes: {str(exc)[:300]}") from exc

    background_tasks.add_task(process_session, session_id, None, gps_path, image_paths)
    return SessionUploadOut(id=session_id, status="queued", message="Imágenes recibidas; el análisis se procesa en segundo plano.")


@app.get("/api/defects", response_model=list[DefectOut])
def list_defects(
    session_id: UUID | None = Query(default=None),
    review_status: str | None = Query(default=None),
    defect_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DefectOut]:
    query = select(RoadDefect).order_by(RoadDefect.created_at.desc()).limit(500)
    if session_id:
        query = query.where(RoadDefect.session_id == session_id)
    if review_status:
        query = query.where(RoadDefect.review_status == review_status)
    if defect_type:
        query = query.where(RoadDefect.defect_type == defect_type)
    if severity:
        query = query.where(RoadDefect.severity_estimated == severity)
    return [_defect_out(db, item) for item in db.scalars(query).all()]


@app.get("/api/defects/{defect_id}", response_model=DefectOut)
def get_defect(defect_id: UUID, db: Session = Depends(get_db)) -> DefectOut:
    defect = db.get(RoadDefect, defect_id)
    if defect is None:
        raise HTTPException(status_code=404, detail="No se encontró la incidencia.")
    return _defect_out(db, defect)


@app.patch("/api/defects/{defect_id}", response_model=DefectOut)
def update_defect(defect_id: UUID, payload: DefectUpdate, db: Session = Depends(get_db)) -> DefectOut:
    defect = db.get(RoadDefect, defect_id)
    if defect is None:
        raise HTTPException(status_code=404, detail="No se encontró la incidencia.")
    updates = payload.model_dump(exclude_unset=True)
    latitude = updates.pop("latitude", None)
    longitude = updates.pop("longitude", None)
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Envía latitude y longitude juntas para cambiar la ubicación.")
    for field, value in updates.items():
        setattr(defect, field, value)
    if latitude is not None and longitude is not None:
        defect.location = from_shape(Point(longitude, latitude), srid=4326)
    db.commit()
    db.refresh(defect)
    return _defect_out(db, defect)
