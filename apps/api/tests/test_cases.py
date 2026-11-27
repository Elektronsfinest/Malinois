from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from main import app
from models import Case, User
from security import hash_password


@pytest.fixture()
def cases_env(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, int]], None, None]:
    db_file = tmp_path / "cases_test.db"
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

    ids: dict[str, int] = {}
    with TestingSessionLocal() as db:
        admin = User(
            email="admin@cases.local",
            hashed_password=hash_password("AdminPass123!"),
            is_active=True,
            role="admin",
            supervisor_id=None,
            must_change_password=False,
        )
        sup1 = User(
            email="sup1@cases.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        sup2 = User(
            email="sup2@cases.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([admin, sup1, sup2])
        db.flush()

        u1 = User(
            email="u1@cases.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=sup1.id,
            must_change_password=False,
        )
        u2_inactive = User(
            email="u2_inactive@cases.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=False,
            role="user",
            supervisor_id=sup1.id,
            must_change_password=False,
        )
        u3_other = User(
            email="u3_other@cases.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=sup2.id,
            must_change_password=False,
        )
        db.add_all([u1, u2_inactive, u3_other])
        db.flush()

        today = date.today()
        now = datetime.now(timezone.utc)
        c1 = Case(
            case_number="C-001",
            title="Sprawa U1 (zaległa)",
            client_name="Jan Kowalski",
            assigned_to=u1.id,
            deadline=today - timedelta(days=2),
            date_filed=today - timedelta(days=20),
            status="open",
            archived=False,
            version=1,
            extra_fields={"APROBANT": "Lewandowska"},
            created_at=now,
            updated_at=now,
        )
        c2 = Case(
            case_number="C-002",
            title="Sprawa Sup1 (bez terminu)",
            client_name="Anna Nowak",
            assigned_to=sup1.id,
            deadline=None,
            date_filed=None,
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c3 = Case(
            case_number="C-003",
            title="Sprawa U3 (inny zespół)",
            client_name="Marek Wiśniewski",
            assigned_to=u3_other.id,
            deadline=today + timedelta(days=5),
            date_filed=today - timedelta(days=5),
            status="open",
            archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        c4_archived = Case(
            case_number="C-004",
            title="Sprawa U1 (zarchiwizowana)",
            client_name="Zofia Zielińska",
            assigned_to=u1.id,
            deadline=today + timedelta(days=10),
            date_filed=today - timedelta(days=10),
            status="closed",
            archived=True,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add_all([c1, c2, c3, c4_archived])
        db.commit()

        ids = {
            "admin": admin.id,
            "sup1": sup1.id,
            "sup2": sup2.id,
            "u1": u1.id,
            "u2_inactive": u2_inactive.id,
            "u3_other": u3_other.id,
            "c1": c1.id,
            "c2": c2.id,
            "c3": c3.id,
            "c4_archived": c4_archived.id,
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


class TestCaseListingAndVisibility:
    def test_role_scoped_listing_sorting_and_archived_exclusion(self, cases_env):
        client, _, ids = cases_env
        u1_h = _login(client, "u1@cases.local", "UserPass1234!")
        sup1_h = _login(client, "sup1@cases.local", "SuperPass123!")
        admin_h = _login(client, "admin@cases.local", "AdminPass123!")

        # User sees only own active cases (c4_archived excluded)
        u1_res = client.get("/api/cases", headers=u1_h)
        assert u1_res.status_code == 200
        u1_body = u1_res.json()
        assert u1_body["total"] == 1
        assert u1_body["page"] == 1
        assert u1_body["page_size"] == 50
        assert [i["id"] for i in u1_body["items"]] == [ids["c1"]]
        assert u1_body["items"][0]["assigned_to_email"] == "u1@cases.local"
        assert u1_body["items"][0]["assigned_to_is_active"] is True

        # Supervisor sees own + subordinate (c1 then c2 because NULL deadline is last)
        sup_body = client.get("/api/cases", headers=sup1_h).json()
        assert sup_body["total"] == 2
        assert [i["id"] for i in sup_body["items"]] == [ids["c1"], ids["c2"]]

        # Admin sees all active cases sorted deadline ASC NULLS LAST: c1, c3, c2
        admin_body = client.get("/api/cases", headers=admin_h).json()
        assert admin_body["total"] == 3
        assert [i["id"] for i in admin_body["items"]] == [ids["c1"], ids["c3"], ids["c2"]]

    def test_out_of_scope_single_case_returns_404_anti_enumeration(self, cases_env):
        client, _, ids = cases_env
        u1_h = _login(client, "u1@cases.local", "UserPass1234!")
        sup1_h = _login(client, "sup1@cases.local", "SuperPass123!")

        assert client.get(f"/api/cases/{ids['c3']}", headers=u1_h).status_code == 404
        assert client.get(f"/api/cases/{ids['c2']}", headers=u1_h).status_code == 404
        assert client.get(f"/api/cases/{ids['c3']}", headers=sup1_h).status_code == 404
        assert client.get("/api/cases/99999", headers=sup1_h).status_code == 404


class TestAssignableUsersAndCaseCreation:
    def test_assignable_users_includes_inactive_for_supervisor_and_admin(self, cases_env):
        client, _, _ = cases_env
        u1_h = _login(client, "u1@cases.local", "UserPass1234!")
        sup1_h = _login(client, "sup1@cases.local", "SuperPass123!")
        admin_h = _login(client, "admin@cases.local", "AdminPass123!")

        assert client.get("/api/users/assignable", headers=u1_h).status_code == 403

        sup_list = client.get("/api/users/assignable", headers=sup1_h).json()
        sup_emails = {u["email"]: u["is_active"] for u in sup_list}
        assert sup_emails == {
            "sup1@cases.local": True,
            "u1@cases.local": True,
            "u2_inactive@cases.local": False,
        }

        admin_list = client.get("/api/users/assignable", headers=admin_h).json()
        assert len(admin_list) == 6
        assert any(u["email"] == "u2_inactive@cases.local" and not u["is_active"] for u in admin_list)

    def test_create_case_rules_for_user_supervisor_and_admin_including_inactive_assignee(
        self, cases_env
    ):
        client, _, ids = cases_env
        u1_h = _login(client, "u1@cases.local", "UserPass1234!")
        sup1_h = _login(client, "sup1@cases.local", "SuperPass123!")
        admin_h = _login(client, "admin@cases.local", "AdminPass123!")

        # Regular user -> 403
        assert (
            client.post(
                "/api/cases",
                headers=u1_h,
                json={"title": "X", "client_name": "Y", "assigned_to": ids["u1"]},
            ).status_code
            == 403
        )

        # Supervisor with non-null deadline -> 403
        assert (
            client.post(
                "/api/cases",
                headers=sup1_h,
                json={
                    "title": "X",
                    "client_name": "Y",
                    "assigned_to": ids["u1"],
                    "deadline": "2027-01-15",
                },
            ).status_code
            == 403
        )

        # Supervisor assigning outside team -> 403
        assert (
            client.post(
                "/api/cases",
                headers=sup1_h,
                json={
                    "title": "X",
                    "client_name": "Y",
                    "assigned_to": ids["u3_other"],
                },
            ).status_code
            == 403
        )

        # Supervisor assigning to INACTIVE direct subordinate with null dates -> 201!
        sup_ok = client.post(
            "/api/cases",
            headers=sup1_h,
            json={
                "title": "Sprawa dla nieaktywnego",
                "client_name": "Piotr Zieliński",
                "assigned_to": ids["u2_inactive"],
                "deadline": None,
                "date_filed": None,
                "extra_fields": {"APROBANT": "Kowalczyk"},
            },
        )
        assert sup_ok.status_code == 201
        body = sup_ok.json()
        assert body["assigned_to"] == ids["u2_inactive"]
        assert body["assigned_to_is_active"] is False
        assert body["version"] == 1
        assert body["extra_fields"] == {"APROBANT": "Kowalczyk"}

        # Admin creating with past deadline + duplicate case_number check
        admin_ok = client.post(
            "/api/cases",
            headers=admin_h,
            json={
                "case_number": "C-ADMIN-1",
                "title": "Pilna zaległa",
                "client_name": "Ewa Kaczmarek",
                "assigned_to": ids["u3_other"],
                "deadline": "2025-01-01",
                "date_filed": "2024-12-01",
            },
        )
        assert admin_ok.status_code == 201

        dup = client.post(
            "/api/cases",
            headers=admin_h,
            json={
                "case_number": "C-ADMIN-1",
                "title": "Duplikat",
                "client_name": "Ewa Kaczmarek",
                "assigned_to": ids["u3_other"],
            },
        )
        assert dup.status_code == 400


class TestCasePatchOptimisticLockingAndDeactivationHook:
    def test_patch_field_permissions_date_reason_archived_and_409_conflict(self, cases_env):
        client, _, ids = cases_env
        u1_h = _login(client, "u1@cases.local", "UserPass1234!")
        admin_h = _login(client, "admin@cases.local", "AdminPass123!")

        # User cannot edit deadline -> 403
        assert (
            client.patch(
                f"/api/cases/{ids['c1']}",
                headers=u1_h,
                json={"version": 1, "deadline": "2027-05-01"},
            ).status_code
            == 403
        )

        # User cannot edit case_number -> 403
        assert (
            client.patch(
                f"/api/cases/{ids['c1']}",
                headers=u1_h,
                json={"version": 1, "case_number": "HACKED"},
            ).status_code
            == 403
        )

        # User edits title + status + extra_fields -> 200, version -> 2
        ok = client.patch(
            f"/api/cases/{ids['c1']}",
            headers=u1_h,
            json={
                "version": 1,
                "title": "Zaktualizowany tytuł",
                "status": "closed",
                "extra_fields": {"APROBANT": "Nowak", "Pesel": "90010112345"},
            },
        )
        assert ok.status_code == 200
        assert ok.json()["version"] == 2
        assert ok.json()["status"] == "closed"

        # Stale version 1 -> 409 Conflict with current object
        conflict = client.patch(
            f"/api/cases/{ids['c1']}",
            headers=u1_h,
            json={"version": 1, "title": "Stara wersja"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["current"]["version"] == 2
        assert conflict.json()["current"]["title"] == "Zaktualizowany tytuł"

        # Admin changing deadline without reason -> 400
        no_reason = client.patch(
            f"/api/cases/{ids['c1']}",
            headers=admin_h,
            json={"version": 2, "deadline": "2027-06-01"},
        )
        assert no_reason.status_code == 400

        # Admin changing deadline WITH reason -> 200, version -> 3
        with_reason = client.patch(
            f"/api/cases/{ids['c1']}",
            headers=admin_h,
            json={
                "version": 2,
                "deadline": "2027-06-01",
                "reason": "Korekta daty z pisma ZUS",
            },
        )
        assert with_reason.status_code == 200
        assert with_reason.json()["version"] == 3
        assert with_reason.json()["deadline"] == "2027-06-01"

        # Archived case cannot be edited -> 400
        archived_patch = client.patch(
            f"/api/cases/{ids['c4_archived']}",
            headers=admin_h,
            json={"version": 1, "title": "Próba edycji archiwum"},
        )
        assert archived_patch.status_code == 400

    def test_deactivating_user_with_active_cases_enforces_reassignment_and_increments_version(
        self, cases_env
    ):
        client, SessionLocal, ids = cases_env
        admin_h = _login(client, "admin@cases.local", "AdminPass123!")

        # Deactivating u1 without reassign_cases_to -> 409 with blocking_case_ids=[c1]
        # (c4_archived is archived, so it must NOT block!)
        conflict = client.patch(
            f"/api/admin/users/{ids['u1']}",
            headers=admin_h,
            json={"is_active": False},
        )
        assert conflict.status_code == 409
        assert conflict.json()["blocking_case_ids"] == [ids["c1"]]

        # Deactivating u1 WITH reassign_cases_to=sup1 -> 200, c1 reassigned & version=2
        ok = client.patch(
            f"/api/admin/users/{ids['u1']}",
            headers=admin_h,
            json={"is_active": False, "reassign_cases_to": ids["sup1"]},
        )
        assert ok.status_code == 200
        assert ok.json()["is_active"] is False

        with SessionLocal() as db:
            c1 = db.scalar(select(Case).where(Case.id == ids["c1"]))
            assert c1 is not None
            assert c1.assigned_to == ids["sup1"]
            assert c1.version == 2
