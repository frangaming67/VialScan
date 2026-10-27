import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ScanSession(Base):
    __tablename__ = "scan_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    error_message: Mapped[str | None] = mapped_column(Text)

    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    route_points: Mapped[list["RoutePoint"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    road_defects: Mapped[list["RoadDefect"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    session: Mapped[ScanSession] = relationship(back_populates="media_assets")
    frames: Mapped[list["Frame"]] = relationship(back_populates="media_asset", cascade="all, delete-orphan")


class RoutePoint(Base):
    __tablename__ = "route_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    elapsed_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    altitude_m: Mapped[float | None] = mapped_column(Float)
    speed_mps: Mapped[float | None] = mapped_column(Float)
    heading_deg: Mapped[float | None] = mapped_column(Float)

    session: Mapped[ScanSession] = relationship(back_populates="route_points")


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    elapsed_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    route_point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_points.id", ondelete="SET NULL"))
    georeference_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreferenced")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    media_asset: Mapped[MediaAsset] = relationship(back_populates="frames")
    detections: Mapped[list["Detection"]] = relationship(back_populates="frame", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frame_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("frames.id", ondelete="CASCADE"), nullable=False, index=True)
    defect_type: Mapped[str] = mapped_column(String(48), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    region_json: Mapped[dict | None] = mapped_column(JSONB)
    severity_estimated: Mapped[str] = mapped_column(String(16), nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    frame: Mapped[Frame] = relationship(back_populates="detections")
    observations: Mapped[list["DefectObservation"]] = relationship(back_populates="detection", cascade="all, delete-orphan")


class RoadDefect(Base):
    __tablename__ = "road_defects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    defect_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    severity_estimated: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    first_observed_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_observed_at: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_frame_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("frames.id", ondelete="RESTRICT"), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session: Mapped[ScanSession] = relationship(back_populates="road_defects")
    observations: Mapped[list["DefectObservation"]] = relationship(back_populates="road_defect", cascade="all, delete-orphan")


class DefectObservation(Base):
    __tablename__ = "defect_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    road_defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("road_defects.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, index=True)

    road_defect: Mapped[RoadDefect] = relationship(back_populates="observations")
    detection: Mapped[Detection] = relationship(back_populates="observations")
