from pathlib import Path
from urllib.parse import quote

import httpx

from ..config import settings


def upload_object(path: str, file_path: Path, content_type: str) -> None:
    if not settings.storage_ready:
        raise RuntimeError("Configura SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y SUPABASE_STORAGE_BUCKET.")
    url = (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
        f"{quote(settings.supabase_storage_bucket, safe='')}/{quote(path, safe='/')}"
    )
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    with file_path.open("rb") as file:
        response = httpx.put(url, headers=headers, content=file, timeout=120)
    response.raise_for_status()


def signed_url(path: str, expires_in: int = 3600) -> str | None:
    if not settings.storage_ready:
        return None
    url = (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/"
        f"{quote(settings.supabase_storage_bucket, safe='')}/{quote(path, safe='/')}"
    )
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }
    try:
        response = httpx.post(url, headers=headers, json={"expiresIn": expires_in}, timeout=15)
        response.raise_for_status()
        signed = response.json().get("signedURL")
        if not signed:
            return None
        return signed if signed.startswith("http") else f"{settings.supabase_url.rstrip('/')}/storage/v1{signed}"
    except httpx.HTTPError:
        return None
