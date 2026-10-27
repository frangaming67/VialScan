from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VialScan API"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "road-evidence"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    frame_interval_seconds: float = 2.0
    max_video_mb: int = 150
    gps_max_gap_seconds: float = 8.0
    gps_interpolation_max_gap_seconds: float = 12.0
    upload_dir: Path = Path("./uploads")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_ready(self) -> bool:
        return bool(self.database_url)

    @property
    def storage_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key and self.supabase_storage_bucket)

    @property
    def analysis_ready(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
