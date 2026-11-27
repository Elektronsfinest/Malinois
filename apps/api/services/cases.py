from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload
from exceptions import StructuredHTTPException
from models import Case, CaseAssignmentHistory, User
from schemas import (
    BulkCaseRequest,
    BulkCaseResponse,
    CaseCreateRequest,
    CaseReassignRequest,
    CaseReassignResponse,
    CaseResponse,
    CaseUpdateRequest,
)
from services.audit import (
    create_initial_case_note,
    log_case_changes,
    record_assignment_change,
)
from services.settings import get_notification_threshold_days

MAX_REASON_LENGTH = 500
MAX_BULK_ITEMS = 200
WARSAW_TZ = ZoneInfo("Europe/Warsaw")


def _today_warsaw() -> date:
    return datetime.now(WARSAW_TZ).date()


def _parse_iso_date_param(value: str | None, param_name: str) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieprawidłowy format daty w parametrze '{param_name}' (oczekiwano YYYY-MM-DD).",
        ) from exc


def serialize_case(case: Case, *, is_readonly_archive: bool = False) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        client_name=case.client_name,
        assigned_to=case.assigned_to,
        assigned_to_email=case.assignee.email,
        assigned_to_is_active=case.assignee.is_active,
        deadline=case.deadline,
        date_filed=case.date_filed,
        status=case.status,  # type: ignore[arg-type]
        archived=case.archived,
        is_readonly_archive=is_readonly_archive,
        version=case.version,
        extra_fields=case.extra_fields,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _get_visible_user_ids(db: Session, actor: User) -> set[int] | None:
    if actor.role == "admin":
        return None
    if actor.role == "supervisor":
        sub_ids = set(
            db.scalars(select(User.id).where(User.supervisor_id == actor.id)).all()
        )
        return {actor.id} | sub_ids
    return {actor.id}


def list_assignable_users(db: Session, actor: User) -> list[User]:
    if actor.role == "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Brak uprawnień do przypisywania spraw.",
        )

    stmt = select(User).order_by(User.is_active.desc(), User.email.asc())
    if actor.role == "supervisor":
        visible_ids = _get_visible_user_ids(db, actor) or {actor.id}
        stmt = stmt.where(User.id.in_(visible_ids))

    return list(db.scalars(stmt).all())


def list_cases(
    db: Session,
    actor: User,
    *,
    page: int = 1,
    page_size: int = 50,
    archived: bool = False,
    q: str | None = None,
    status_filter: str | None = None,
    assigned_to: int | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    overdue: bool | None = None,
    due_soon: bool | None = None,
    sort: str = "deadline_asc",
) -> tuple[list[CaseResponse], int]:
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parametr 'page' musi być >= 1.",
        )
    if page_size < 1 or page_size > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parametr 'page_size' musi być w zakresie 1–200.",
        )

    if status_filter is not None and status_filter not in ("open", "closed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowa wartość parametru 'status' (dozwolone: open, closed).",
        )

    if sort not in ("deadline_asc", "deadline_desc", "updated_at_desc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowa wartość parametru 'sort'.",
        )

    d_from = _parse_iso_date_param(deadline_from, "deadline_from")
    d_to = _parse_iso_date_param(deadline_to, "deadline_to")

    base_stmt = select(Case).where(Case.archived.is_(archived))
    visible_ids = _get_visible_user_ids(db, actor)

    if assigned_to is not None:
        if visible_ids is not None and assigned_to not in visible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Brak uprawnień do filtrowania spraw wybranego użytkownika.",
            )

    if visible_ids is not None:
        if archived:
            past_case_ids = select(CaseAssignmentHistory.case_id).where(
                CaseAssignmentHistory.user_id.in_(visible_ids)
            )
            base_stmt = base_stmt.where(
                or_(
                    Case.assigned_to.in_(visible_ids),
                    Case.id.in_(past_case_ids),
                )
            )
        else:
            base_stmt = base_stmt.where(Case.assigned_to.in_(visible_ids))

    if assigned_to is not None:
        base_stmt = base_stmt.where(Case.assigned_to == assigned_to)

    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                Case.case_number.ilike(pattern),
                Case.title.ilike(pattern),
                Case.client_name.ilike(pattern),
            )
        )

    if status_filter is not None:
        base_stmt = base_stmt.where(Case.status == status_filter)

    if d_from is not None:
        base_stmt = base_stmt.where(Case.deadline.is_not(None), Case.deadline >= d_from)

    if d_to is not None:
        base_stmt = base_stmt.where(Case.deadline.is_not(None), Case.deadline <= d_to)

    if overdue is True:
        today = _today_warsaw()
        base_stmt = base_stmt.where(
            Case.status == "open",
            Case.deadline.is_not(None),
            Case.deadline < today,
        )

    if due_soon is True:
        today = _today_warsaw()
        threshold = get_notification_threshold_days(db)
        horizon = today + timedelta(days=threshold)
        base_stmt = base_stmt.where(
            Case.status == "open",
            Case.deadline.is_not(None),
            Case.deadline >= today,
            Case.deadline <= horizon,
        )

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = int(db.scalar(count_stmt) or 0)

    if sort == "deadline_desc":
        order_clauses = (Case.deadline.is_(None).asc(), Case.deadline.desc(), Case.id.asc())
    elif sort == "updated_at_desc":
        order_clauses = (Case.updated_at.desc(), Case.id.desc())
    else:
        order_clauses = (Case.deadline.is_(None).asc(), Case.deadline.asc(), Case.id.asc())

    items_stmt = (
        base_stmt.options(joinedload(Case.assignee))
        .order_by(*order_clauses)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    cases = list(db.scalars(items_stmt).unique().all())
    serialized: list[CaseResponse] = []
    for c in cases:
        readonly = bool(
            archived and visible_ids is not None and c.assigned_to not in visible_ids
        )
        serialized.append(serialize_case(c, is_readonly_archive=readonly))
    return serialized, total


def get_case_in_scope(db: Session, actor: User, case_id: int) -> Case:
    """Returns a case within the caller's active/current management scope, or 404."""
    case = db.scalar(
        select(Case).options(joinedload(Case.assignee)).where(Case.id == case_id)
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sprawa nie została znaleziona.",
        )

    visible_ids = _get_visible_user_ids(db, actor)
    if visible_ids is not None and case.assigned_to not in visible_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sprawa nie została znaleziona.",
        )

    return case


def get_case_readable(db: Session, actor: User, case_id: int) -> tuple[Case, bool]:
    """Returns (case, is_readonly_archive), allowing past assignees on archived cases."""
    case = db.scalar(
        select(Case).options(joinedload(Case.assignee)).where(Case.id == case_id)
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sprawa nie została znaleziona.",
        )

    visible_ids = _get_visible_user_ids(db, actor)
    if visible_ids is None or case.assigned_to in visible_ids:
        return case, False

    if case.archived:
        was_assigned = db.scalar(
            select(CaseAssignmentHistory.id).where(
                CaseAssignmentHistory.case_id == case.id,
                CaseAssignmentHistory.user_id.in_(visible_ids),
            )
        )
        if was_assigned is not None:
            return case, True

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Sprawa nie została znaleziona.",
    )


def create_case(
    db: Session,
    actor: User,
    payload: CaseCreateRequest,
    *,
    allow_imported_dates: bool = False,
) -> CaseResponse:
    if actor.role == "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Użytkownik z rolą 'user' nie może tworzyć spraw.",
        )

    if not payload.title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tytuł sprawy jest wymagany.",
        )
    if not payload.client_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nazwa klienta jest wymagana.",
        )

    if (
        actor.role != "admin"
        and not allow_imported_dates
        and (payload.deadline is not None or payload.date_filed is not None)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko administrator może ustawiać daty (termin realizacji / data wpływu).",
        )

    assignee = db.scalar(select(User).where(User.id == payload.assigned_to))
    if assignee is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wybrany użytkownik przypisany do sprawy nie istnieje.",
        )

    if actor.role == "supervisor":
        visible_ids = _get_visible_user_ids(db, actor) or {actor.id}
        if assignee.id not in visible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Przełożony może przypisywać sprawy wyłącznie sobie lub swoim bezpośrednim podwładnym.",
            )

    if payload.case_number is not None:
        existing = db.scalar(
            select(Case.id).where(Case.case_number == payload.case_number)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sprawa o takim numerze już istnieje.",
            )

    now = datetime.now(timezone.utc)
    case = Case(
        case_number=payload.case_number,
        title=payload.title,
        client_name=payload.client_name,
        assigned_to=assignee.id,
        deadline=payload.deadline,
        date_filed=payload.date_filed,
        status=payload.status,
        archived=False,
        version=1,
        extra_fields=payload.extra_fields,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.flush()

    record_assignment_change(db, case_id=case.id, new_user_id=assignee.id)
    log_case_changes(
        db=db,
        case_id=case.id,
        actor_id=actor.id,
        changes={"created": (None, case.title)},
    )

    db.commit()
    db.refresh(case)
    case.assignee = assignee
    return serialize_case(case)


def update_case(
    db: Session,
    actor: User,
    case_id: int,
    payload: CaseUpdateRequest,
) -> CaseResponse:
    case = get_case_in_scope(db, actor, case_id)

    if case.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zarchiwizowanej sprawy nie można edytować. Najpierw ją przywróć.",
        )

    if case.version != payload.version:
        raise StructuredHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Konflikt wersji: sprawa została zmodyfikowana przez innego użytkownika.",
                "current": serialize_case(case).model_dump(mode="json"),
            },
        )

    provided = payload.model_fields_set

    if actor.role != "admin":
        if "deadline" in provided and payload.deadline != case.deadline:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tylko administrator może modyfikować termin realizacji.",
            )
        if "date_filed" in provided and payload.date_filed != case.date_filed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tylko administrator może modyfikować datę wpływu.",
            )
        if "case_number" in provided and payload.case_number != case.case_number:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tylko administrator może modyfikować numer sprawy.",
            )
        if "assigned_to" in provided and payload.assigned_to != case.assigned_to:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bezpośrednia zmiana przypisanej osoby w edycji jest dostępna tylko dla administratora.",
            )

    deadline_changed = "deadline" in provided and payload.deadline != case.deadline
    date_filed_changed = "date_filed" in provided and payload.date_filed != case.date_filed
    if deadline_changed or date_filed_changed:
        reason = (payload.reason or "").strip()
        if not reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Zmiana daty wymaga podania powodu (pole 'reason').",
            )
        if len(reason) > MAX_REASON_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Powód zmiany daty nie może przekraczać 500 znaków.",
            )

    changes: dict[str, tuple[Any, Any]] = {}

    if "title" in provided:
        if not payload.title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tytuł sprawy nie może być pusty.",
            )
        if payload.title != case.title:
            changes["title"] = (case.title, payload.title)
            case.title = payload.title

    if "client_name" in provided:
        if not payload.client_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nazwa klienta nie może być pusta.",
            )
        if payload.client_name != case.client_name:
            changes["client_name"] = (case.client_name, payload.client_name)
            case.client_name = payload.client_name

    if "status" in provided and payload.status is not None and payload.status != case.status:
        changes["status"] = (case.status, payload.status)
        case.status = payload.status

    if "extra_fields" in provided and payload.extra_fields != case.extra_fields:
        changes["extra_fields"] = (case.extra_fields, payload.extra_fields)
        case.extra_fields = payload.extra_fields

    if "case_number" in provided and payload.case_number != case.case_number:
        if payload.case_number is not None:
            existing = db.scalar(
                select(Case.id).where(
                    Case.case_number == payload.case_number, Case.id != case.id
                )
            )
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sprawa o takim numerze już istnieje.",
                )
        changes["case_number"] = (case.case_number, payload.case_number)
        case.case_number = payload.case_number

    if "assigned_to" in provided and payload.assigned_to is not None and payload.assigned_to != case.assigned_to:
        new_assignee = db.scalar(select(User).where(User.id == payload.assigned_to))
        if new_assignee is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wybrany użytkownik przypisany do sprawy nie istnieje.",
            )
        old_assignee_id = case.assigned_to
        changes["assigned_to"] = (old_assignee_id, new_assignee.id)
        case.assigned_to = new_assignee.id
        case.assignee = new_assignee
        record_assignment_change(
            db,
            case_id=case.id,
            new_user_id=new_assignee.id,
            old_user_id=old_assignee_id,
        )

    if deadline_changed:
        changes["deadline"] = (case.deadline, payload.deadline)
        case.deadline = payload.deadline

    if date_filed_changed:
        changes["date_filed"] = (case.date_filed, payload.date_filed)
        case.date_filed = payload.date_filed

    case.version += 1
    case.updated_at = datetime.now(timezone.utc)

    if changes:
        log_case_changes(
            db=db,
            case_id=case.id,
            actor_id=actor.id,
            changes=changes,
            reason=payload.reason if (deadline_changed or date_filed_changed) else None,
        )

    db.commit()
    db.refresh(case)
    return serialize_case(case)


def archive_case(db: Session, actor: User, case_id: int, version: int) -> CaseResponse:
    case = get_case_in_scope(db, actor, case_id)

    if case.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sprawa jest już zarchiwizowana.",
        )

    if case.version != version:
        raise StructuredHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Konflikt wersji: sprawa została zmodyfikowana przez innego użytkownika.",
                "current": serialize_case(case).model_dump(mode="json"),
            },
        )

    case.archived = True
    case.version += 1
    case.updated_at = datetime.now(timezone.utc)

    log_case_changes(
        db=db,
        case_id=case.id,
        actor_id=actor.id,
        changes={"archived": (False, True)},
    )
    db.commit()
    db.refresh(case)
    return serialize_case(case)


def restore_case(db: Session, actor: User, case_id: int, version: int) -> CaseResponse:
    from services import notifications as notif_service

    case, is_readonly = get_case_readable(db, actor, case_id)

    if actor.role == "user" or is_readonly:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko przełożony aktualnie przypisanego pracownika lub administrator może przywrócić sprawę.",
        )

    if not case.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sprawa nie jest zarchiwizowana.",
        )

    if case.version != version:
        raise StructuredHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Konflikt wersji: sprawa została zmodyfikowana przez innego użytkownika.",
                "current": serialize_case(case).model_dump(mode="json"),
            },
        )

    case.archived = False
    case.version += 1
    case.updated_at = datetime.now(timezone.utc)

    notif_service.clear_case_dismissals(db, case.id)
    log_case_changes(
        db=db,
        case_id=case.id,
        actor_id=actor.id,
        changes={"archived": (True, False)},
    )
    db.commit()
    db.refresh(case)
    return serialize_case(case)


def bulk_cases(
    db: Session,
    actor: User,
    payload: BulkCaseRequest,
) -> BulkCaseResponse:
    from services import notifications as notif_service

    if payload.action not in ("set_status", "archive", "restore"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowa akcja zbiorcza (dozwolone: set_status, archive, restore).",
        )

    if not payload.items or len(payload.items) > MAX_BULK_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Liczba spraw w operacji zbiorczej musi wynosić od 1 do {MAX_BULK_ITEMS}.",
        )

    new_status: str | None = None
    if payload.action == "set_status":
        params = payload.params or {}
        raw_status = params.get("status")
        if raw_status not in ("open", "closed"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parametr 'status' musi mieć wartość 'open' lub 'closed'.",
            )
        new_status = str(raw_status)

    if payload.action == "restore" and actor.role == "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zwykły użytkownik nie może przywracać spraw z archiwum.",
        )

    # Deduplicate while preserving order
    seen_ids: set[int] = set()
    unique_items = []
    for item in payload.items:
        if item.id in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lista zawiera zduplikowane identyfikatory spraw.",
            )
        seen_ids.add(item.id)
        unique_items.append(item)

    cases_by_id = {
        c.id: c
        for c in db.scalars(select(Case).where(Case.id.in_(seen_ids))).all()
    }
    visible_ids = _get_visible_user_ids(db, actor)

    for item in unique_items:
        case = cases_by_id.get(item.id)
        if case is None or (visible_ids is not None and case.assigned_to not in visible_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Co najmniej jedna z wybranych spraw nie istnieje lub jest poza Twoim zakresem uprawnień.",
            )

    conflicts = [
        {
            "case_id": item.id,
            "expected_version": item.version,
            "current_version": cases_by_id[item.id].version,
        }
        for item in unique_items
        if cases_by_id[item.id].version != item.version
    ]
    if conflicts:
        raise StructuredHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Konflikt wersji w operacji zbiorczej: część spraw została zmieniona przez innego użytkownika.",
                "conflicts": conflicts,
            },
        )

    now = datetime.now(timezone.utc)
    for item in unique_items:
        case = cases_by_id[item.id]
        if payload.action == "set_status":
            if case.archived:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nie można zmieniać statusu zarchiwizowanej sprawy.",
                )
            old_status = case.status
            case.status = new_status or case.status
            case.version += 1
            case.updated_at = now
            if old_status != case.status:
                log_case_changes(
                    db=db,
                    case_id=case.id,
                    actor_id=actor.id,
                    changes={"status": (old_status, case.status)},
                )
        elif payload.action == "archive":
            old_arch = case.archived
            case.archived = True
            case.version += 1
            case.updated_at = now
            if not old_arch:
                log_case_changes(
                    db=db,
                    case_id=case.id,
                    actor_id=actor.id,
                    changes={"archived": (False, True)},
                )
        elif payload.action == "restore":
            old_arch = case.archived
            case.archived = False
            case.version += 1
            case.updated_at = now
            notif_service.clear_case_dismissals(db, case.id)
            if old_arch:
                log_case_changes(
                    db=db,
                    case_id=case.id,
                    actor_id=actor.id,
                    changes={"archived": (True, False)},
                )

    db.commit()
    return BulkCaseResponse(
        success=True,
        affected_count=len(unique_items),
        action=payload.action,
    )


def reassign_cases(
    db: Session,
    actor: User,
    payload: CaseReassignRequest,
) -> CaseReassignResponse:
    if actor.role == "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zwykły użytkownik nie może przepisywać spraw.",
        )

    if not payload.items or len(payload.items) > MAX_BULK_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Liczba spraw do przepisania musi wynosić od 1 do {MAX_BULK_ITEMS}.",
        )

    if payload.reason and len(payload.reason) > MAX_REASON_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Powód przepisania nie może przekraczać 500 znaków.",
        )

    target_user = db.scalar(select(User).where(User.id == payload.new_assigned_to))
    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wybrany docelowy pracownik nie istnieje lub jest nieaktywny.",
        )

    visible_ids = _get_visible_user_ids(db, actor)
    if actor.role == "supervisor" and visible_ids is not None and target_user.id not in visible_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Przełożony może przepisywać sprawy wyłącznie sobie lub swoim bezpośrednim podwładnym.",
        )

    seen_ids: set[int] = set()
    unique_items = []
    for item in payload.items:
        if item.id in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lista zawiera zduplikowane identyfikatory spraw.",
            )
        seen_ids.add(item.id)
        unique_items.append(item)

    cases_by_id = {
        c.id: c
        for c in db.scalars(select(Case).where(Case.id.in_(seen_ids))).all()
    }

    for item in unique_items:
        case = cases_by_id.get(item.id)
        if case is None or (visible_ids is not None and case.assigned_to not in visible_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Co najmniej jedna z wybranych spraw nie istnieje lub jest poza Twoim zakresem uprawnień.",
            )

    conflicts = [
        {
            "case_id": item.id,
            "expected_version": item.version,
            "current_version": cases_by_id[item.id].version,
        }
        for item in unique_items
        if cases_by_id[item.id].version != item.version
    ]
    if conflicts:
        raise StructuredHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Konflikt wersji podczas przepisywania: część spraw została zmieniona przez innego użytkownika.",
                "conflicts": conflicts,
            },
        )

    now = datetime.now(timezone.utc)
    for item in unique_items:
        case = cases_by_id[item.id]
        old_assignee_id = case.assigned_to
        case.assigned_to = target_user.id
        case.version += 1
        case.updated_at = now
        if old_assignee_id != target_user.id:
            record_assignment_change(
                db,
                case_id=case.id,
                new_user_id=target_user.id,
                old_user_id=old_assignee_id,
            )
            log_case_changes(
                db=db,
                case_id=case.id,
                actor_id=actor.id,
                changes={"assigned_to": (old_assignee_id, target_user.id)},
                reason=payload.reason,
            )
        if payload.reason:
            create_initial_case_note(
                db=db,
                case_id=case.id,
                actor_id=actor.id,
                content=f"Przepisano sprawę na {target_user.email}. Powód: {payload.reason}",
            )

    db.commit()
    return CaseReassignResponse(
        success=True,
        reassigned_count=len(unique_items),
        new_assigned_to=target_user.id,
        new_assigned_to_email=target_user.email,
    )
