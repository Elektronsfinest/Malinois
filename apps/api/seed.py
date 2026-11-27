from datetime import date, datetime, timedelta, timezone
import os
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Case, User
from security import hash_password

DEMO_PASSWORD = "Secret123!"


def is_demo_seeding_enabled() -> bool:
    env = os.getenv("ENV", "development").lower()
    seed_flag = os.getenv("SEED_DEMO_USER", "").lower()
    if seed_flag in ("false", "0", "no"):
        return False
    if seed_flag in ("true", "1", "yes"):
        return True
    return env in ("development", "dev", "local", "test")


def _get_or_create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: str = "user",
    supervisor_id: int | None = None,
) -> User:
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        if supervisor_id is not None and existing_user.supervisor_id is None:
            existing_user.supervisor_id = supervisor_id
        return existing_user

    user = User(
        email=email,
        hashed_password=hash_password(password),
        is_active=True,
        role=role,
        supervisor_id=supervisor_id,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    return user


def _get_or_create_case(
    db: Session,
    *,
    case_number: str,
    title: str,
    client_name: str,
    assigned_to: int,
    deadline: date | None,
    date_filed: date | None,
    extra_fields: dict[str, str] | None = None,
) -> None:
    existing = db.scalar(select(Case.id).where(Case.case_number == case_number))
    if existing is not None:
        return

    now = datetime.now(timezone.utc)
    db.add(
        Case(
            case_number=case_number,
            title=title,
            client_name=client_name,
            assigned_to=assigned_to,
            deadline=deadline,
            date_filed=date_filed,
            status="open",
            archived=False,
            version=1,
            extra_fields=extra_fields,
            created_at=now,
            updated_at=now,
        )
    )


def seed_initial_user(db: Session) -> None:
    _get_or_create_user(
        db,
        email="admin@example.com",
        password=DEMO_PASSWORD,
        role="admin",
    )
    supervisor = _get_or_create_user(
        db,
        email="sup@example.com",
        password=DEMO_PASSWORD,
        role="supervisor",
    )
    trainee = _get_or_create_user(
        db,
        email="trainee@example.com",
        password=DEMO_PASSWORD,
        role="user",
        supervisor_id=supervisor.id,
    )

    if inspect(engine).has_table("cases"):
        today = date.today()
        _get_or_create_case(
            db,
            case_number="ZUS-2026-0001",
            title="ERN – Wniosek o emeryturę",
            client_name="Jan Kowalski",
            assigned_to=trainee.id,
            deadline=today - timedelta(days=3),
            date_filed=today - timedelta(days=30),
            extra_fields={"APROBANT": "Lewandowska", "OFE": "Tak"},
        )
        _get_or_create_case(
            db,
            case_number="ZUS-2026-0002",
            title="ERN – Przeliczenie kapitału",
            client_name="Anna Nowak",
            assigned_to=trainee.id,
            deadline=today + timedelta(days=3),
            date_filed=today - timedelta(days=14),
            extra_fields={"APROBANT": "Kowalczyk", "Składki": "Do weryfikacji"},
        )
        _get_or_create_case(
            db,
            case_number="ZUS-2026-0003",
            title="Renta z tytułu niezdolności",
            client_name="Marek Wiśniewski",
            assigned_to=supervisor.id,
            deadline=today + timedelta(days=20),
            date_filed=today - timedelta(days=5),
            extra_fields={"APROBANT": "Zielińska"},
        )
        _get_or_create_case(
            db,
            case_number="ZUS-2026-0004",
            title="Nowa sprawa – oczekuje na daty",
            client_name="Katarzyna Wójcik",
            assigned_to=trainee.id,
            deadline=None,
            date_filed=None,
            extra_fields={"INNE": "Przekazane do uzupełnienia terminu"},
        )

    db.commit()


def ensure_seeded() -> None:
    if not is_demo_seeding_enabled():
        return

    if not inspect(engine).has_table("users"):
        return

    db = SessionLocal()
    try:
        seed_initial_user(db)
    finally:
        db.close()


if __name__ == "__main__":
    ensure_seeded()
