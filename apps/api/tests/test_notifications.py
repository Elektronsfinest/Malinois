from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from main import app
from models import Case, User
from security import hash_password
from services import notifications as notif_service


@pytest.fixture()
def notif_env(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, int]], None, None]:
    db_file = tmp_path / "notif_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def _set_fk_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    today = notif_service.get_today_warsaw()
    now = datetime.now(timezone.utc)

    with TestingSessionLocal() as db:
        admin = User(
            email="admin@notif.local",
            hashed_password=hash_password("AdminPass123!"),
            is_active=True,
            role="admin",
            supervisor_id=None,
            must_change_password=False,
        )
        sup = User(
            email="sup@notif.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([admin, sup])
        db.flush()

        user = User(
            email="user@notif.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=sup.id,
            must_change_password=False,
        )
        other = User(
            email="other@notif.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([user, other])
        db.flush()

        c_overdue = Case(
            case_number="N-1",
            title="Sprawa zaległa",
            client_name="Jan Kowalski",
            assigned_to=user.id,
            deadline=today - timedelta(days=3),
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c_today = Case(
            case_number="N-2",
            title="Termin dzisiaj",
            client_name="Anna Nowak",
            assigned_to=user.id,
            deadline=today,
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c_upcoming = Case(
            case_number="N-3",
            title="Za 5 dni",
            client_name="Piotr Zieliński",
            assigned_to=sup.id,
            deadline=today + timedelta(days=5),
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c_far = Case(
            case_number="N-4",
            title="Daleki termin",
            client_name="Ewa Daleka",
            assigned_to=user.id,
            deadline=today + timedelta(days=15),
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c_closed = Case(
            case_number="N-5",
            title="Zamknięta zaległa",
            client_name="Marek Zamknięty",
            assigned_to=user.id,
            deadline=today - timedelta(days=1),
            status="closed",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c_other_overdue = Case(
            case_number="N-6",
            title="Obca zaległa",
            client_name="Zofia Obca",
            assigned_to=other.id,
            deadline=today - timedelta(days=5),
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add_all([c_overdue, c_today, c_upcoming, c_far, c_closed, c_other_overdue])
        db.commit()

        ids = {
            "admin": admin.id,
            "sup": sup.id,
            "user": user.id,
            "c_overdue": c_overdue.id,
            "c_today": c_today.id,
            "c_upcoming": c_upcoming.id,
            "c_far": c_far.id,
            "c_closed": c_closed.id,
            "c_other_overdue": c_other_overdue.id,
        }

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app), TestingSessionLocal, ids
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    res = client.post("/api/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


class TestNotificationsDerivationAndScoping:
    def test_role_scoping_urgency_and_sorting(self, notif_env):
        client, _, ids = notif_env
        user_h = _login(client, "user@notif.local", "UserPass1234!")
        sup_h = _login(client, "sup@notif.local", "SuperPass123!")
        admin_h = _login(client, "admin@notif.local", "AdminPass123!")

        # User sees only own open non-archived within threshold (overdue + today; excludes far + closed)
        u_items = client.get("/api/notifications", headers=user_h).json()
        assert [i["case_id"] for i in u_items] == [ids["c_overdue"], ids["c_today"]]
        assert u_items[0]["urgency"] == "overdue"
        assert u_items[0]["days_remaining"] == -3
        assert u_items[0]["assigned_to_email"] == "user@notif.local"
        assert u_items[1]["urgency"] == "upcoming"
        assert u_items[1]["days_remaining"] == 0

        # Supervisor sees own + subordinate's sorted by deadline ASC
        s_items = client.get("/api/notifications", headers=sup_h).json()
        assert [i["case_id"] for i in s_items] == [
            ids["c_overdue"],
            ids["c_today"],
            ids["c_upcoming"],
        ]

        # Admin sees all (including c_other_overdue at -5 days first!)
        a_items = client.get("/api/notifications", headers=admin_h).json()
        assert [i["case_id"] for i in a_items] == [
            ids["c_other_overdue"],
            ids["c_overdue"],
            ids["c_today"],
            ids["c_upcoming"],
        ]


class TestNotificationsDismissalLifecycle:
    def test_per_user_dismiss_idempotency_errors_and_reset_rules(self, notif_env):
        client, SessionLocal, ids = notif_env
        user_h = _login(client, "user@notif.local", "UserPass1234!")
        sup_h = _login(client, "sup@notif.local", "SuperPass123!")
        admin_h = _login(client, "admin@notif.local", "AdminPass123!")

        # Out-of-scope case -> 404
        assert (
            client.post(
                f"/api/notifications/{ids['c_other_overdue']}/dismiss", headers=user_h
            ).status_code
            == 404
        )

        # Case with no active notification (far future / closed) -> 400
        assert (
            client.post(f"/api/notifications/{ids['c_far']}/dismiss", headers=user_h).status_code
            == 400
        )
        assert (
            client.post(f"/api/notifications/{ids['c_closed']}/dismiss", headers=user_h).status_code
            == 400
        )

        # User dismisses c_today -> 204, idempotent on second call
        assert (
            client.post(f"/api/notifications/{ids['c_today']}/dismiss", headers=user_h).status_code
            == 204
        )
        assert (
            client.post(f"/api/notifications/{ids['c_today']}/dismiss", headers=user_h).status_code
            == 204
        )

        # Hidden for user, still visible for supervisor!
        u_ids = [i["case_id"] for i in client.get("/api/notifications", headers=user_h).json()]
        s_ids = [i["case_id"] for i in client.get("/api/notifications", headers=sup_h).json()]
        assert ids["c_today"] not in u_ids
        assert ids["c_today"] in s_ids

        # Routine non-deadline edit (title) does NOT reset dismissal
        assert (
            client.patch(
                f"/api/cases/{ids['c_today']}",
                headers=user_h,
                json={"version": 1, "title": "Zmieniony tytuł bez zmiany daty"},
            ).status_code
            == 200
        )
        u_ids_after_title = [
            i["case_id"] for i in client.get("/api/notifications", headers=user_h).json()
        ]
        assert ids["c_today"] not in u_ids_after_title

        # State transition upcoming -> overdue (tomorrow!) automatically reactivates!
        tomorrow = notif_service.get_today_warsaw() + timedelta(days=1)
        with SessionLocal() as db:
            user_obj = db.get(User, ids["user"])
            assert user_obj is not None
            tomorrow_notifs = notif_service.list_active_notifications(
                db, user_obj, today_warsaw=tomorrow
            )
            assert any(
                n.case_id == ids["c_today"] and n.urgency == "overdue"
                for n in tomorrow_notifs
            )

        # Admin changing deadline resets dismissal cleanly
        new_deadline = (notif_service.get_today_warsaw() + timedelta(days=2)).isoformat()
        assert (
            client.patch(
                f"/api/cases/{ids['c_today']}",
                headers=admin_h,
                json={
                    "version": 2,
                    "deadline": new_deadline,
                    "reason": "Zmiana terminu ZUS",
                },
            ).status_code
            == 200
        )
        u_ids_after_deadline = [
            i["case_id"] for i in client.get("/api/notifications", headers=user_h).json()
        ]
        assert ids["c_today"] in u_ids_after_deadline
