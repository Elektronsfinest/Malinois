import asyncio
from datetime import datetime, timedelta, timezone
import gzip
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from database import BASE_DIR, DATABASE_URL, SessionLocal
from models import BackupLog, User
from security import verify_password
from services.audit import log_admin_action

logger = logging.getLogger("malinois.backups")

ALLOWED_BACKUP_TYPES = ("automated", "manual", "pre_import")
FILENAME_PATTERN = re.compile(
    r"^malinois_backup_\d{8}_\d{6}(?:_\d+)?_(automated|manual|pre_import)\.(sql|sqlite)\.gz$"
)
RETENTION_DAYS = 14


def get_backup_dir() -> Path:
    configured = os.getenv("BACKUP_DIR")
    if configured:
        return Path(configured)
    return BASE_DIR / "backups"


def _resolve_sqlite_path(db_url: str) -> Path | None:
    if not db_url.startswith("sqlite:///"):
        return None
    raw = db_url[len("sqlite:///") :]
    if raw == ":memory:":
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p


def _unique_backup_path(backup_dir: Path, backup_type: str, ext: str) -> tuple[str, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    candidate = f"malinois_backup_{stamp}_{backup_type}.{ext}.gz"
    dest = backup_dir / candidate
    counter = 1
    while dest.exists():
        candidate = f"malinois_backup_{stamp}_{counter}_{backup_type}.{ext}.gz"
        dest = backup_dir / candidate
        counter += 1
    return candidate, dest


def create_backup(
    db: Session,
    *,
    backup_type: str,
    created_by_id: int | None = None,
) -> BackupLog:
    if backup_type not in ALLOWED_BACKUP_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy typ kopii zapasowej.",
        )

    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    sqlite_path = _resolve_sqlite_path(DATABASE_URL)
    if sqlite_path is not None:
        filename, dest_path = _unique_backup_path(backup_dir, backup_type, "sqlite")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            src_conn = sqlite3.connect(str(sqlite_path))
            dst_conn = sqlite3.connect(str(tmp_path))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()
            with tmp_path.open("rb") as f_in, gzip.open(dest_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        finally:
            tmp_path.unlink(missing_ok=True)
    elif DATABASE_URL.startswith("postgresql"):
        filename, dest_path = _unique_backup_path(backup_dir, backup_type, "sql")
        pg_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
        proc = subprocess.run(
            ["pg_dump", pg_url],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Nie udało się utworzyć kopii bazy PostgreSQL (pg_dump).",
            )
        with gzip.open(dest_path, "wb") as f_out:
            f_out.write(proc.stdout)
    else:
        # In-memory SQLite fallback (rare)
        filename, dest_path = _unique_backup_path(backup_dir, backup_type, "sqlite")
        with gzip.open(dest_path, "wb") as f_out:
            f_out.write(b"")

    size_bytes = dest_path.stat().st_size
    entry = BackupLog(
        filename=filename,
        size_bytes=size_bytes,
        backup_type=backup_type,
        created_at=datetime.now(timezone.utc),
        created_by_id=created_by_id,
    )
    db.add(entry)
    db.flush()
    if created_by_id is not None and backup_type == "manual":
        log_admin_action(
            db=db,
            actor_id=created_by_id,
            action="backup_created",
            details={"filename": filename, "backup_type": backup_type},
        )
    db.commit()
    db.refresh(entry)
    return entry


def list_backups(db: Session) -> list[BackupLog]:
    return list(
        db.scalars(
            select(BackupLog).order_by(BackupLog.created_at.desc(), BackupLog.id.desc())
        ).all()
    )


def validate_backup_filename(filename: str) -> str:
    if (
        not filename
        or ".." in filename
        or "/" in filename
        or "\\" in filename
        or not FILENAME_PATTERN.match(filename)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowa nazwa pliku kopii zapasowej.",
        )
    return filename


def get_backup_file_for_download(
    db: Session,
    *,
    actor: User,
    filename: str,
    password: str,
) -> Path:
    safe_name = validate_backup_filename(filename)

    if not verify_password(password, actor.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowe hasło administratora.",
        )

    backup_dir = get_backup_dir().resolve()
    target = (backup_dir / safe_name).resolve()
    if target.parent != backup_dir or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plik kopii zapasowej nie został znaleziony.",
        )

    log_admin_action(
        db=db,
        actor_id=actor.id,
        action="backup_downloaded",
        details={"filename": safe_name},
    )
    db.commit()
    return target


def prune_old_backups(db: Session, *, retention_days: int = RETENTION_DAYS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    backup_dir = get_backup_dir()
    removed = 0

    expired_logs = list(
        db.scalars(select(BackupLog).where(BackupLog.created_at < cutoff)).all()
    )
    for entry in expired_logs:
        if FILENAME_PATTERN.match(entry.filename):
            candidate = backup_dir / entry.filename
            if candidate.is_file():
                candidate.unlink(missing_ok=True)
                removed += 1
        db.delete(entry)
    if expired_logs:
        db.commit()

    if backup_dir.is_dir():
        cutoff_ts = cutoff.timestamp()
        for path in backup_dir.iterdir():
            if path.is_file() and FILENAME_PATTERN.match(path.name):
                if path.stat().st_mtime < cutoff_ts:
                    path.unlink(missing_ok=True)
                    removed += 1
    return removed


def _seconds_until_next_0200_utc(now: datetime | None = None) -> float:
    current = now or datetime.now(timezone.utc)
    target = current.replace(hour=2, minute=0, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return max(1.0, (target - current).total_seconds())


async def nightly_backup_loop() -> None:
    while True:
        delay = _seconds_until_next_0200_utc()
        await asyncio.sleep(delay)
        db = SessionLocal()
        try:
            create_backup(db, backup_type="automated", created_by_id=None)
            prune_old_backups(db, retention_days=RETENTION_DAYS)
        except Exception:
            logger.exception("Nightly automated backup failed")
        finally:
            db.close()
