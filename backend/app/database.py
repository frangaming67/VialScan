from collections.abc import Generator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


def _database_url() -> str:
    url = settings.database_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


engine = create_engine(_database_url(), pool_pre_ping=True, pool_recycle=300) if settings.database_ready else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL no está configurada. Usa el modo de demostración o completa backend/.env.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
