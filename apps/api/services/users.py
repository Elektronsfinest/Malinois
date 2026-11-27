from datetime import datetime, timezone
import re
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from exceptions import StructuredHTTPException
from models import Case, User
from schemas import AdminUserCreateRequest, AdminUserUpdateRequest, UserRole
from security import generate_temporary_password, hash_password, validate_password_policy
from services.audit import log_admin_action, log_case_changes, record_assignment_change

MANAGER_ROLES = {"supervisor", "admin"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_blocking_case_ids(db: Session, user_id: int) -> list[int]:
    """Returns active (non-archived) case IDs owned by user_id."""
    return list(
        db.scalars(
            select(Case.id)
            .where(Case.assigned_to == user_id, Case.archived.is_(False))
            .order_by(Case.id.asc())
        ).all()
    )


def _validate_supervisor_target(
    db: Session,
    supervisor_id: int,
    *,
    exclude_user_id: int | None = None,
) -> User:
    if exclude_user_id is not None and supervisor_id == exclude_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik nie może być własnym przełożonym.",
        )

    supervisor = db.scalar(select(User).where(User.id == supervisor_id))
    if (
        supervisor is None
        or not supervisor.is_active
        or supervisor.role not in MANAGER_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wybrany przełożony nie istnieje, jest nieaktywny lub nie ma roli supervisor/admin.",
        )
    return supervisor


def list_users(
    db: Session,
    *,
    role: UserRole | None = None,
    supervisor_id: int | None = None,
    is_active: bool | None = None,
) -> list[User]:
    stmt = select(User).order_by(User.id.asc())
    if role is not None:
        stmt = stmt.where(User.role == role)
    if supervisor_id is not None:
        stmt = stmt.where(User.supervisor_id == supervisor_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    return list(db.scalars(stmt).all())


def create_user(
    db: Session,
    payload: AdminUserCreateRequest,
    *,
    actor: User,
) -> User:
    if not _EMAIL_RE.match(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Niepoprawny format adresu email.",
        )

    existing = db.scalar(
        select(User).where(func.lower(User.email) == payload.email.lower())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o tym adresie email już istnieje.",
        )

    try:
        validate_password_policy(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if payload.role != "user" and payload.supervisor_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tylko użytkownik z rolą 'user' może mieć przypisanego przełożonego.",
        )

    if payload.supervisor_id is not None:
        _validate_supervisor_target(db, payload.supervisor_id)

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_active=True,
        role=payload.role,
        supervisor_id=payload.supervisor_id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    log_admin_action(
        db=db,
        actor_id=actor.id,
        action="user_created",
        target_user_id=user.id,
        details={"role": user.role, "supervisor_id": user.supervisor_id},
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: int,
    payload: AdminUserUpdateRequest,
    *,
    actor: User,
) -> User:
    target = db.scalar(select(User).where(User.id == user_id))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie został znaleziony.",
        )

    old_state = {
        "role": target.role,
        "supervisor_id": target.supervisor_id,
        "is_active": target.is_active,
    }

    new_role: str = payload.role if payload.role is not None else target.role
    new_is_active: bool = (
        payload.is_active if payload.is_active is not None else target.is_active
    )

    # Admin self-lockout guard
    if target.id == actor.id:
        if not new_is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrator nie może dezaktywować własnego konta.",
            )
        if new_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrator nie może obniżyć własnej roli.",
            )

    # Last active admin guard
    removing_admin_access = (
        target.role == "admin"
        and target.is_active
        and (new_role != "admin" or not new_is_active)
    )
    if removing_admin_access:
        active_admin_count = db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin", User.is_active.is_(True)
            )
        )
        if (active_admin_count or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="W systemie musi pozostać co najmniej jeden aktywny administrator.",
            )

    # Supervisor hierarchy rules (1-level: only 'user' may have supervisor_id)
    supervisor_field_provided = "supervisor_id" in payload.model_fields_set
    if new_role in MANAGER_ROLES:
        if supervisor_field_provided and payload.supervisor_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Użytkownik z rolą 'supervisor' lub 'admin' nie może mieć przełożonego.",
            )
        new_supervisor_id = None
    else:
        if supervisor_field_provided:
            if payload.supervisor_id is not None:
                _validate_supervisor_target(
                    db, payload.supervisor_id, exclude_user_id=target.id
                )
            new_supervisor_id = payload.supervisor_id
        else:
            new_supervisor_id = target.supervisor_id

    # Validate reassignment targets if provided
    if payload.reassign_cases_to is not None:
        if payload.reassign_cases_to == target.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nie można przepisać spraw na tego samego użytkownika.",
            )
        case_target = db.scalar(select(User).where(User.id == payload.reassign_cases_to))
        if case_target is None or not case_target.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Docelowy użytkownik do przepisania spraw nie istnieje lub jest nieaktywny.",
            )

    if payload.reassign_subordinates_to is not None:
        _validate_supervisor_target(
            db, payload.reassign_subordinates_to, exclude_user_id=target.id
        )

    is_deactivating = target.is_active and not new_is_active
    is_demoting_from_manager = target.role in MANAGER_ROLES and new_role == "user"

    subordinates: list[User] = []
    if is_deactivating or is_demoting_from_manager:
        subordinates = list(
            db.scalars(select(User).where(User.supervisor_id == target.id)).all()
        )
    blocking_subordinate_ids = [u.id for u in subordinates]
    blocking_case_ids = get_blocking_case_ids(db, target.id) if is_deactivating else []

    missing_case_target = bool(blocking_case_ids) and payload.reassign_cases_to is None
    missing_subordinate_target = (
        bool(blocking_subordinate_ids) and payload.reassign_subordinates_to is None
    )
    if missing_case_target or missing_subordinate_target:
        raise StructuredHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Operacja wymaga przepisania aktywnych spraw lub podwładnych.",
                "blocking_case_ids": blocking_case_ids,
                "blocking_subordinate_ids": blocking_subordinate_ids,
            },
        )

    # Atomic update + reassignment
    if subordinates and payload.reassign_subordinates_to is not None:
        for sub in subordinates:
            sub.supervisor_id = payload.reassign_subordinates_to

    if blocking_case_ids and payload.reassign_cases_to is not None:
        now = datetime.now(timezone.utc)
        active_cases = list(
            db.scalars(select(Case).where(Case.id.in_(blocking_case_ids))).all()
        )
        for case in active_cases:
            old_assignee = case.assigned_to
            case.assigned_to = payload.reassign_cases_to
            case.version += 1
            case.updated_at = now
            record_assignment_change(
                db,
                case_id=case.id,
                new_user_id=payload.reassign_cases_to,
                old_user_id=old_assignee,
            )
            log_case_changes(
                db=db,
                case_id=case.id,
                actor_id=actor.id,
                changes={"assigned_to": (old_assignee, payload.reassign_cases_to)},
            )

    target.role = new_role
    target.supervisor_id = new_supervisor_id
    target.is_active = new_is_active

    if old_state["role"] != target.role:
        log_admin_action(
            db=db,
            actor_id=actor.id,
            action="role_changed",
            target_user_id=target.id,
            details={"old_role": old_state["role"], "new_role": target.role},
        )
    if old_state["supervisor_id"] != target.supervisor_id:
        log_admin_action(
            db=db,
            actor_id=actor.id,
            action="supervisor_changed",
            target_user_id=target.id,
            details={
                "old_supervisor_id": old_state["supervisor_id"],
                "new_supervisor_id": target.supervisor_id,
            },
        )
    if old_state["is_active"] != target.is_active:
        log_admin_action(
            db=db,
            actor_id=actor.id,
            action="user_activated" if target.is_active else "user_deactivated",
            target_user_id=target.id,
            details={
                "reassigned_subordinate_ids": blocking_subordinate_ids,
                "reassign_subordinates_to": payload.reassign_subordinates_to,
                "reassigned_case_ids": blocking_case_ids,
                "reassign_cases_to": payload.reassign_cases_to,
            },
        )

    db.commit()
    db.refresh(target)
    return target


def reset_user_password(db: Session, user_id: int, *, actor: User) -> str:
    if user_id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie możesz zresetować własnego hasła w panelu administratora — użyj Ustawień.",
        )

    target = db.scalar(select(User).where(User.id == user_id))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Użytkownik nie został znaleziony.",
        )

    temp_password = generate_temporary_password(16)
    target.hashed_password = hash_password(temp_password)
    target.must_change_password = True

    log_admin_action(
        db=db,
        actor_id=actor.id,
        action="password_reset",
        target_user_id=target.id,
        details={"must_change_password": True},
    )
    db.commit()
    return temp_password
