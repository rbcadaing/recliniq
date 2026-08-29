import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import settings

ALLOWED = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
MAX_BYTES = 10 * 1024 * 1024


def save_upload(tenant_id: int, visit_id: int, upload: UploadFile) -> tuple[str, str, str, int]:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File type not allowed")
    data = upload.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty file")
    stored = f"{uuid.uuid4().hex}{ALLOWED[content_type]}"
    dest_dir = Path(settings.upload_dir) / str(tenant_id) / str(visit_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / stored
    path.write_bytes(data)
    filename = upload.filename or stored
    return filename, stored, content_type, len(data)


def read_stored(tenant_id: int, visit_id: int, stored_name: str) -> bytes:
    path = Path(settings.upload_dir) / str(tenant_id) / str(visit_id) / stored_name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return path.read_bytes()
