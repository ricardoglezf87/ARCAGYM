from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.engine import make_url

from app.config import settings
from app.dependencies import require_user, templates
from app.models import User


router = APIRouter()


def _sqlite_database_path() -> Path | None:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite"):
        return None

    database = url.database
    if not database or database == ":memory:":
        return None

    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def _create_sqlite_backup(source_path: Path) -> tuple[bytes, str]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    download_name = f"arcagym-backup-{timestamp}.db"
    backup_path = source_path.parent / f".arcagym-backup-{timestamp}-{uuid.uuid4().hex}.db"

    with closing(sqlite3.connect(source_path)) as source_connection:
        with closing(sqlite3.connect(backup_path)) as backup_connection:
            source_connection.backup(backup_connection)

    try:
        backup_content = backup_path.read_bytes()
    finally:
        _remove_file(backup_path)

    return backup_content, download_name


@router.get("/backup")
def backup_page(request: Request, user: User = Depends(require_user)):
    database_path = _sqlite_database_path()
    backup_available = bool(database_path and database_path.exists())
    return templates.TemplateResponse(
        "backup.html",
        {
            "request": request,
            "user": user,
            "backup_available": backup_available,
            "database_name": database_path.name if database_path else None,
        },
    )


@router.get("/backup/download")
def download_backup(user: User = Depends(require_user)):
    database_path = _sqlite_database_path()
    if not database_path or not database_path.exists():
        raise HTTPException(status_code=404, detail="Base de datos SQLite no encontrada")

    backup_content, download_name = _create_sqlite_backup(database_path)
    return Response(
        content=backup_content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
