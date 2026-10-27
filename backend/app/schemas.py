from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


DefectType = Literal["pothole", "crack", "patch", "deformation", "other"]
Severity = Literal["low", "medium", "high", "unknown"]
ReviewStatus = Literal["pending", "confirmed", "dismissed"]


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class DefectUpdate(BaseModel):
    review_status: ReviewStatus | None = None
    defect_type: DefectType | None = None
    severity_estimated: Severity | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class DefectOut(BaseModel):
    id: UUID
    session_id: UUID
    defect_type: str
    severity_estimated: str
    severity_score: float
    review_status: str
    description: str
    first_observed_at: float
    last_observed_at: float
    confidence: float
    latitude: float | None = None
    longitude: float | None = None
    evidence_url: str | None = None
    is_synthetic: bool = False


class SessionOut(BaseModel):
    id: UUID
    name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    defects: list[DefectOut] = []


class SessionUploadOut(BaseModel):
    id: UUID
    status: str
    message: str
