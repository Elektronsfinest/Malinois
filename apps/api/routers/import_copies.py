import io
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import get_current_user, require_role
from schemas import (
    WorkingCopyCommitResponse,
    WorkingCopyDetailResponse,
    WorkingCopyPatchRequest,
    WorkingCopySummaryResponse,
)
from services import working_copies as wc_service

router = APIRouter(prefix="/api/import/copies", tags=["import-copies"])


@router.get("", response_model=list[WorkingCopySummaryResponse])
def list_working_copies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkingCopySummaryResponse]:
    return wc_service.list_copies(db, current_user)


@router.post(
    "/upload",
    response_model=WorkingCopyDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_working_copy(
    file: UploadFile = File(...),
    default_assigned_to: int | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "supervisor")),
) -> WorkingCopyDetailResponse:
    raw_bytes = await file.read()
    return wc_service.create_copy_from_upload(
        db,
        current_user,
        filename=file.filename,
        content_type=file.content_type,
        raw_bytes=raw_bytes,
        default_assigned_to=default_assigned_to,
    )


@router.post(
    "/from-cases",
    response_model=WorkingCopyDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def snapshot_working_copy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkingCopyDetailResponse:
    return wc_service.create_copy_from_cases(db, current_user)


@router.get("/{copy_id}", response_model=WorkingCopyDetailResponse)
def get_working_copy(
    copy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkingCopyDetailResponse:
    copy = wc_service.get_copy_owned(db, current_user, copy_id)
    return wc_service._to_detail(copy)


@router.patch("/{copy_id}", response_model=WorkingCopyDetailResponse)
def patch_working_copy(
    copy_id: int,
    payload: WorkingCopyPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkingCopyDetailResponse:
    return wc_service.patch_copy(db, current_user, copy_id, payload)


@router.delete("/{copy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_working_copy(
    copy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    wc_service.delete_copy(db, current_user, copy_id)


@router.get("/{copy_id}/download")
def download_working_copy(
    copy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    data, filename = wc_service.download_copy_bytes(db, current_user, copy_id)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{copy_id}/commit", response_model=WorkingCopyCommitResponse)
def commit_working_copy(
    copy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkingCopyCommitResponse:
    return wc_service.commit_copy(db, current_user, copy_id)
