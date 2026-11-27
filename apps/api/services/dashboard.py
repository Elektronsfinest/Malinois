from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import case as sa_case, func, select
from sqlalchemy.orm import Session
from models import Case, User
from schemas import DashboardSummaryResponse, TeamMemberSummaryResponse
from services.cases import _get_visible_user_ids
from services.settings import get_notification_threshold_days, get_system_setting

WARSAW_TZ = ZoneInfo("Europe/Warsaw")


def get_dashboard_summary(db: Session, actor: User) -> DashboardSummaryResponse:
    now_warsaw = datetime.now(WARSAW_TZ)
    today_warsaw: date = now_warsaw.date()
    month_start_warsaw = datetime(
        now_warsaw.year, now_warsaw.month, 1, 0, 0, 0, tzinfo=WARSAW_TZ
    )
    month_start_utc = month_start_warsaw.astimezone(timezone.utc)

    threshold_days = get_notification_threshold_days(db)
    horizon_date = today_warsaw + timedelta(days=threshold_days)

    visible_ids = _get_visible_user_ids(db, actor)

    agg_stmt = (
        select(
            Case.assigned_to.label("user_id"),
            func.count(Case.id).label("total_cases"),
            func.sum(sa_case((Case.status == "open", 1), else_=0)).label("open_cases"),
            func.sum(
                sa_case(
                    (
                        (Case.status == "open")
                        & (Case.deadline.is_not(None))
                        & (Case.deadline < today_warsaw),
                        1,
                    ),
                    else_=0,
                )
            ).label("overdue_cases"),
            func.sum(
                sa_case(
                    (
                        (Case.status == "open")
                        & (Case.deadline.is_not(None))
                        & (Case.deadline >= today_warsaw)
                        & (Case.deadline <= horizon_date),
                        1,
                    ),
                    else_=0,
                )
            ).label("due_soon"),
            func.sum(
                sa_case(
                    (
                        (Case.status == "closed") & (Case.updated_at >= month_start_utc),
                        1,
                    ),
                    else_=0,
                )
            ).label("closed_this_month"),
        )
        .where(Case.archived.is_(False))
        .group_by(Case.assigned_to)
    )

    if visible_ids is not None:
        agg_stmt = agg_stmt.where(Case.assigned_to.in_(visible_ids))

    rows = db.execute(agg_stmt).all()

    by_user: dict[int, dict[str, int]] = {}
    total_all = 0
    total_open = 0
    total_overdue = 0
    total_due_soon = 0
    total_closed_month = 0

    for row in rows:
        uid = int(row.user_id)
        t_cases = int(row.total_cases or 0)
        o_cases = int(row.open_cases or 0)
        ov_cases = int(row.overdue_cases or 0)
        ds_cases = int(row.due_soon or 0)
        cm_cases = int(row.closed_this_month or 0)

        by_user[uid] = {
            "open_cases": o_cases,
            "overdue_cases": ov_cases,
            "due_soon": ds_cases,
        }
        total_all += t_cases
        total_open += o_cases
        total_overdue += ov_cases
        total_due_soon += ds_cases
        total_closed_month += cm_cases

    team_summary: list[TeamMemberSummaryResponse] | None = None
    total_cases_out: int | None = None
    import_last_at: str | None = None

    if actor.role == "supervisor":
        member_ids = visible_ids or {actor.id}
        members = list(
            db.scalars(
                select(User)
                .where(User.id.in_(member_ids))
                .order_by(User.is_active.desc(), User.email.asc())
            ).all()
        )
        team_summary = [
            TeamMemberSummaryResponse(
                user_id=m.id,
                email=m.email,
                is_active=m.is_active,
                open_cases=by_user.get(m.id, {}).get("open_cases", 0),
                overdue_cases=by_user.get(m.id, {}).get("overdue_cases", 0),
                due_soon=by_user.get(m.id, {}).get("due_soon", 0),
            )
            for m in members
        ]
    elif actor.role == "admin":
        users_with_open = {
            uid for uid, stats in by_user.items() if stats["open_cases"] > 0
        }
        all_users = list(
            db.scalars(
                select(User).order_by(User.is_active.desc(), User.email.asc())
            ).all()
        )
        team_summary = [
            TeamMemberSummaryResponse(
                user_id=u.id,
                email=u.email,
                is_active=u.is_active,
                open_cases=by_user.get(u.id, {}).get("open_cases", 0),
                overdue_cases=by_user.get(u.id, {}).get("overdue_cases", 0),
                due_soon=by_user.get(u.id, {}).get("due_soon", 0),
            )
            for u in all_users
            if u.is_active or u.id in users_with_open
        ]
        total_cases_out = total_all
        import_last_at = get_system_setting(db, "last_import_at")

    return DashboardSummaryResponse(
        notification_threshold_days=threshold_days,
        open_cases=total_open,
        overdue_cases=total_overdue,
        due_soon=total_due_soon,
        closed_this_month=total_closed_month,
        team_summary=team_summary,
        total_cases=total_cases_out,
        import_last_at=import_last_at,
    )
