from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from models import AdminAuditLog, CaseEditLog, CaseNote, User
from schemas import (
    AdminAuditLogListResponse,
    AdminAuditLogResponse,
    CaseEditLogResponse,
    CaseNoteCreateRequest,
    CaseNoteResponse,
    PersonNoteCreateRequest,
)
from services import cases as case_service

MAX_NOTE_LENGTH = 2000


def _validate_note_content(content: str) -> str:
    text = content.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Treść notatki nie może być pusta.",
        )
    if len(text) > MAX_NOTE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Treść notatki nie może przekraczać 2000 znaków.",
        )
    return text


def _serialize_note(note: CaseNote) -> CaseNoteResponse:
    return CaseNoteResponse(
        id=note.id,
        case_id=note.case_id,
        subject_user_id=note.subject_user_id,
        subject_email=note.subject_user.email if note.subject_user is not None else None,
        content=note.content,
        author_id=note.author_id,
        author_email=note.author.email,
        created_at=note.created_at,
    )


def _can_access_person_subject(actor: User, target: User) -> bool:
    if actor.role == "admin":
        return True
    if actor.id == target.id:
        return True
    if actor.role == "supervisor" and target.supervisor_id == actor.id:
        return True
    return False


# ── Spec 009: Case Edit History & Admin Audit Log ────────────────────────────

def list_case_history(
    db: Session,
    actor: User,
    case_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[CaseEditLogResponse]:
    case_service.get_case_readable(db, actor, case_id)
    bounded_limit = max(1, min(limit, 200))
    bounded_offset = max(0, offset)

    rows = list(
        db.scalars(
            select(CaseEditLog)
            .options(joinedload(CaseEditLog.user))
            .where(CaseEditLog.case_id == case_id)
            .order_by(CaseEditLog.changed_at.desc(), CaseEditLog.id.desc())
            .offset(bounded_offset)
            .limit(bounded_limit)
        )
        .unique()
        .all()
    )
    return [
        CaseEditLogResponse(
            id=r.id,
            field_name=r.field_name,
            old_value=r.old_value,
            new_value=r.new_value,
            reason=r.reason,
            changed_by_email=r.user.email,
            changed_at=r.changed_at,
        )
        for r in rows
    ]


def list_admin_audit_log(
    db: Session,
    *,
    action: str | None = None,
    target_user_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> AdminAuditLogListResponse:
    if page < 1:
        raise HTTPException(status_code=400, detail="Parametr 'page' musi być >= 1.")
    if page_size < 1 or page_size > 200:
        raise HTTPException(
            status_code=400, detail="Parametr 'page_size' musi być w zakresie 1–200."
        )

    stmt = select(AdminAuditLog)
    if action:
        stmt = stmt.where(AdminAuditLog.action == action)
    if target_user_id is not None:
        stmt = stmt.where(AdminAuditLog.target_user_id == target_user_id)

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(
            stmt.options(joinedload(AdminAuditLog.actor))
            .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )
    items = [
        AdminAuditLogResponse(
            id=r.id,
            actor_email=r.actor.email,
            action=r.action,
            target_user_id=r.target_user_id,
            details=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return AdminAuditLogListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


# ── Spec 010: Case & Person Notes ────────────────────────────────────────────

def list_case_notes(db: Session, actor: User, case_id: int) -> list[CaseNoteResponse]:
    case_service.get_case_readable(db, actor, case_id)
    notes = list(
        db.scalars(
            select(CaseNote)
            .options(joinedload(CaseNote.author), joinedload(CaseNote.subject_user))
            .where(CaseNote.case_id == case_id)
            .order_by(CaseNote.created_at.desc(), CaseNote.id.desc())
        )
        .unique()
        .all()
    )
    return [_serialize_note(n) for n in notes]


def create_case_note(
    db: Session,
    actor: User,
    case_id: int,
    payload: CaseNoteCreateRequest,
) -> CaseNoteResponse:
    case = case_service.get_case_in_scope(db, actor, case_id)
    if case.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie można dodawać notatek do zarchiwizowanej sprawy. Najpierw ją przywróć.",
        )

    content = _validate_note_content(payload.content)

    subject_user: User | None = None
    if payload.subject_user_id is not None:
        subject_user = db.scalar(select(User).where(User.id == payload.subject_user_id))
        if subject_user is None or not _can_access_person_subject(actor, subject_user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wybrany użytkownik w polu 'Dotyczy osoby' nie istnieje lub jest poza Twoim zakresem.",
            )

    note = CaseNote(
        case_id=case.id,
        subject_user_id=subject_user.id if subject_user is not None else None,
        author_id=actor.id,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    note.author = actor
    note.subject_user = subject_user
    return _serialize_note(note)


def list_person_notes(db: Session, actor: User, user_id: int) -> list[CaseNoteResponse]:
    target = db.scalar(select(User).where(User.id == user_id))
    if target is None or not _can_access_person_subject(actor, target):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie został znaleziony.",
        )

    notes = list(
        db.scalars(
            select(CaseNote)
            .options(joinedload(CaseNote.author), joinedload(CaseNote.subject_user))
            .where(CaseNote.case_id.is_(None), CaseNote.subject_user_id == target.id)
            .order_by(CaseNote.created_at.desc(), CaseNote.id.desc())
        )
        .unique()
        .all()
    )
    return [_serialize_note(n) for n in notes]


def create_person_note(
    db: Session,
    actor: User,
    user_id: int,
    payload: PersonNoteCreateRequest,
) -> CaseNoteResponse:
    target = db.scalar(select(User).where(User.id == user_id))
    if target is None or not _can_access_person_subject(actor, target):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie został znaleziony.",
        )

    content = _validate_note_content(payload.content)
    note = CaseNote(
        case_id=None,
        subject_user_id=target.id,
        author_id=actor.id,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    note.author = actor
    note.subject_user = target
    return _serialize_note(note)


def delete_note(db: Session, actor: User, note_id: int) -> None:
    note = db.scalar(
        select(CaseNote)
        .options(joinedload(CaseNote.subject_user))
        .where(CaseNote.id == note_id)
    )
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notatka nie została znaleziona.",
        )

    # Verify visibility first (404 if out of scope)
    visible = False
    if actor.role == "admin" or note.author_id == actor.id:
        visible = True
    elif note.case_id is not None:
        try:
            case_service.get_case_readable(db, actor, note.case_id)
            visible = True
        except HTTPException:
            visible = False
    elif note.subject_user is not None:
        visible = _can_access_person_subject(actor, note.subject_user)

    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notatka nie została znaleziona.",
        )

    # Only author or admin may delete a visible note (allowed even if case is archived)
    if actor.role != "admin" and note.author_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko autor notatki lub administrator może ją usunąć.",
        )

    db.delete(note)
    db.commit()
