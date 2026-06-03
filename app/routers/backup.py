from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.engine import make_url

from app.config import settings
from app.dependencies import require_user, templates
from app.models import User


router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = PROJECT_ROOT / "backup"


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


def _unique_backup_path(download_name: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / download_name
    if not backup_path.exists():
        return backup_path

    stem = backup_path.stem
    suffix = backup_path.suffix
    counter = 2
    while True:
        candidate = BACKUP_DIR / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _list_backups() -> list[dict[str, str | int]]:
    if not BACKUP_DIR.exists():
        return []

    backups = sorted(BACKUP_DIR.glob("*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [
        {
            "name": path.name,
            "size_kb": max(1, round(path.stat().st_size / 1024)),
            "created_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
        }
        for path in backups
    ]


def _create_sqlite_backup(source_path: Path) -> tuple[Path, str]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    download_name = f"arcagym-backup-{timestamp}.db"
    backup_path = _unique_backup_path(download_name)

    with closing(sqlite3.connect(source_path)) as source_connection:
        with closing(sqlite3.connect(backup_path)) as backup_connection:
            source_connection.backup(backup_connection)

    return backup_path, backup_path.name


def _backup_response(backup_path: Path) -> Response:
    return Response(
        content=backup_path.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{backup_path.name}"'},
    )


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
            "backup_dir": BACKUP_DIR,
            "backups": _list_backups(),
        },
    )


@router.get("/backup/download")
def download_backup(user: User = Depends(require_user)):
    database_path = _sqlite_database_path()
    if not database_path or not database_path.exists():
        raise HTTPException(status_code=404, detail="Base de datos SQLite no encontrada")

    backup_path, _download_name = _create_sqlite_backup(database_path)
    return _backup_response(backup_path)


@router.get("/backup/files/{filename}")
def download_existing_backup(filename: str, user: User = Depends(require_user)):
    backup_path = (BACKUP_DIR / Path(filename).name).resolve()
    if backup_path.parent != BACKUP_DIR.resolve() or backup_path.suffix != ".db" or not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup no encontrado")
    return _backup_response(backup_path)
