from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import get_current_user, require_role
from schemas import (
    AdminAuditLogListResponse,
    CaseEditLogResponse,
    CaseNoteCreateRequest,
    CaseNoteResponse,
    PersonNoteCreateRequest,
)
from services import history_notes as hn_service

router = APIRouter(prefix="/api", tags=["history-and-notes"])


@router.get("/cases/{case_id}/history", response_model=list[CaseEditLogResponse])
def get_case_history(
    case_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseEditLogResponse]:
    return hn_service.list_case_history(
        db, current_user, case_id, limit=limit, offset=offset
    )


@router.get("/admin/audit-log", response_model=AdminAuditLogListResponse)
def get_admin_audit_log(
    action: str | None = None,
    target_user_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> AdminAuditLogListResponse:
    return hn_service.list_admin_audit_log(
        db,
        action=action,
        target_user_id=target_user_id,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}/notes", response_model=list[CaseNoteResponse])
def list_case_notes(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseNoteResponse]:
    return hn_service.list_case_notes(db, current_user, case_id)


@router.post(
    "/cases/{case_id}/notes",
    response_model=CaseNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_note(
    case_id: int,
    payload: CaseNoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseNoteResponse:
    return hn_service.create_case_note(db, current_user, case_id, payload)


@router.get("/users/{user_id}/notes", response_model=list[CaseNoteResponse])
def list_person_notes(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseNoteResponse]:
    return hn_service.list_person_notes(db, current_user, user_id)


@router.post(
    "/users/{user_id}/notes",
    response_model=CaseNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_person_note(
    user_id: int,
    payload: PersonNoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseNoteResponse:
    return hn_service.create_person_note(db, current_user, user_id, payload)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    hn_service.delete_note(db, current_user, note_id)
