import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db
from .demo import DEMO
from .models import Frame, MediaAsset, RoadDefect, ScanSession
from .schemas import DefectOut, DefectUpdate, SessionCreate, SessionOut, SessionUploadOut
from .services.processor import process_session
from .services.storage import signed_url, upload_object

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
    return SessionOut(
        id=session.id, name=session.name, status=session.status, started_at=session.started_at,
        finished_at=session.finished_at, error_message=session.error_message,
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
        "missing_variables": list(dict.fromkeys(missing)),
        "frame_interval_seconds": settings.frame_interval_seconds,
        "model": settings.openai_model if settings.analysis_ready else None,
    }


@app.get("/api/demo")
def demo_data() -> dict:
    return DEMO


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
