from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload
from models import Case, NotificationDismissal, User
from schemas import NotificationItemResponse, NotificationUrgency
from services import cases as case_service

WARSAW_TZ = ZoneInfo("Europe/Warsaw")
DEFAULT_NOTIFICATION_THRESHOLD_DAYS = 7


def get_today_warsaw() -> date:
    return datetime.now(WARSAW_TZ).date()


def get_notification_threshold_days(db: Session) -> int:
    from services import settings as settings_service

    return settings_service.get_notification_threshold_days(db)


def _classify_case_notification(
    case: Case,
    *,
    today_warsaw: date,
    threshold_days: int,
) -> tuple[int, NotificationUrgency] | None:
    if case.archived or case.status == "closed" or case.deadline is None:
        return None
    days_remaining = (case.deadline - today_warsaw).days
    if days_remaining > threshold_days:
        return None
    urgency: NotificationUrgency = "overdue" if days_remaining < 0 else "upcoming"
    return days_remaining, urgency


def list_active_notifications(
    db: Session,
    actor: User,
    *,
    today_warsaw: date | None = None,
) -> list[NotificationItemResponse]:
    today = today_warsaw or get_today_warsaw()
    threshold_days = get_notification_threshold_days(db)

    stmt = (
        select(Case)
        .options(joinedload(Case.assignee))
        .where(
            Case.archived.is_(False),
            Case.status != "closed",
            Case.deadline.is_not(None),
        )
        .order_by(Case.deadline.asc(), Case.id.asc())
    )

    visible_ids = case_service._get_visible_user_ids(db, actor)
    if visible_ids is not None:
        stmt = stmt.where(Case.assigned_to.in_(visible_ids))

    cases = list(db.scalars(stmt).unique().all())
    if not cases:
        return []

    case_ids = [c.id for c in cases]
    dismissals = db.scalars(
        select(NotificationDismissal).where(
            NotificationDismissal.user_id == actor.id,
            NotificationDismissal.case_id.in_(case_ids),
        )
    ).all()
    dismissed_keys = {
        (d.case_id, d.deadline_snapshot, d.state) for d in dismissals
    }

    results: list[NotificationItemResponse] = []
    for c in cases:
        classified = _classify_case_notification(
            c, today_warsaw=today, threshold_days=threshold_days
        )
        if classified is None or c.deadline is None:
            continue
        days_remaining, urgency = classified
        if (c.id, c.deadline, urgency) in dismissed_keys:
            continue

        results.append(
            NotificationItemResponse(
                case_id=c.id,
                case_title=c.title,
                client_name=c.client_name,
                assigned_to_email=c.assignee.email,
                deadline=c.deadline,
                days_remaining=days_remaining,
                urgency=urgency,
                version=c.version,
            )
        )

    return results


def dismiss_notification(
    db: Session,
    actor: User,
    case_id: int,
    *,
    today_warsaw: date | None = None,
) -> None:
    case = case_service.get_case_in_scope(db, actor, case_id)
    today = today_warsaw or get_today_warsaw()
    threshold_days = get_notification_threshold_days(db)

    classified = _classify_case_notification(
        case, today_warsaw=today, threshold_days=threshold_days
    )
    if classified is None or case.deadline is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ta sprawa nie ma aktywnego powiadomienia o terminie.",
        )

    _, urgency = classified

    existing = db.scalar(
        select(NotificationDismissal).where(
            NotificationDismissal.user_id == actor.id,
            NotificationDismissal.case_id == case.id,
            NotificationDismissal.deadline_snapshot == case.deadline,
            NotificationDismissal.state == urgency,
        )
    )
    if existing is not None:
        return  # Idempotent 204

    db.add(
        NotificationDismissal(
            user_id=actor.id,
            case_id=case.id,
            deadline_snapshot=case.deadline,
            state=urgency,
            dismissed_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def clear_case_dismissals(db: Session, case_id: int) -> None:
    """Hook for Spec 006 (archive restore). Deletes prior dismissals for a case."""
    db.execute(
        delete(NotificationDismissal).where(NotificationDismissal.case_id == case_id)
    )
    db.flush()
