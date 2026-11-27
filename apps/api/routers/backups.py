from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import require_role
from schemas import BackupDownloadRequest, BackupLogResponse
from services import backups as backup_service

router = APIRouter(prefix="/api/admin", tags=["admin-backups"])


@router.get("/backups", response_model=list[BackupLogResponse])
def list_backups(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> list[BackupLogResponse]:
    rows = backup_service.list_backups(db)
    return [BackupLogResponse.model_validate(r) for r in rows]


@router.post(
    "/backups",
    response_model=BackupLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_manual_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> BackupLogResponse:
    row = backup_service.create_backup(
        db, backup_type="manual", created_by_id=current_user.id
    )
    return BackupLogResponse.model_validate(row)


@router.post("/backups/{filename:path}/download")
def download_backup(
    filename: str,
    payload: BackupDownloadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> FileResponse:
    file_path = backup_service.get_backup_file_for_download(
        db,
        actor=current_user,
        filename=filename,
        password=payload.password,
    )
    return FileResponse(
        path=file_path,
        media_type="application/gzip",
        filename=file_path.name,
        headers={
            "Content-Disposition": f'attachment; filename="{file_path.name}"',
        },
    )
