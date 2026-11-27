from collections.abc import Generator
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from main import app
from models import User
from security import hash_password
from services import notifications as notif_service


@pytest.fixture()
def batch1_env(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, int]], None, None]:
    db_file = tmp_path / "batch1_test.db"
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

    with TestingSessionLocal() as db:
        admin = User(
            email="admin@b1.local",
            hashed_password=hash_password("AdminPass123!"),
            is_active=True,
            role="admin",
            supervisor_id=None,
            must_change_password=False,
        )
        sup1 = User(
            email="sup1@b1.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        sup2 = User(
            email="sup2@b1.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([admin, sup1, sup2])
        db.flush()

        u1 = User(
            email="u1@b1.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=sup1.id,
            must_change_password=False,
        )
        u2 = User(
            email="u2@b1.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=sup2.id,
            must_change_password=False,
        )
        db.add_all([u1, u2])
        db.commit()

        ids = {
            "admin": admin.id,
            "sup1": sup1.id,
            "sup2": sup2.id,
            "u1": u1.id,
            "u2": u2.id,
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


class TestSpec006ArchiveAndPastAssignee:
    def test_archive_restore_notification_reactivation_and_past_assignee_readonly(
        self, batch1_env
    ):
        client, _, ids = batch1_env
        admin_h = _login(client, "admin@b1.local", "AdminPass123!")
        sup1_h = _login(client, "sup1@b1.local", "SuperPass123!")
        u1_h = _login(client, "u1@b1.local", "UserPass1234!")
        u2_h = _login(client, "u2@b1.local", "UserPass1234!")

        today = notif_service.get_today_warsaw()
        created = client.post(
            "/api/cases",
            headers=admin_h,
            json={
                "case_number": "ARC-1",
                "title": "Sprawa do archiwum",
                "client_name": "Jan Kowalski",
                "assigned_to": ids["u1"],
                "deadline": (today - timedelta(days=2)).isoformat(),
            },
        )
        assert created.status_code == 201
        case_id = created.json()["id"]

        # u1 dismisses overdue notification
        assert (
            client.post(f"/api/notifications/{case_id}/dismiss", headers=u1_h).status_code
            == 204
        )
        assert client.get("/api/notifications", headers=u1_h).json() == []

        # u1 archives own open case -> 200, version -> 2
        arc = client.post(
            f"/api/cases/{case_id}/archive", headers=u1_h, json={"version": 1}
        )
        assert arc.status_code == 200
        assert arc.json()["archived"] is True
        assert arc.json()["version"] == 2

        # Double archive -> 400
        assert (
            client.post(
                f"/api/cases/{case_id}/archive", headers=u1_h, json={"version": 2}
            ).status_code
            == 400
        )

        # User cannot restore -> 403
        assert (
            client.post(
                f"/api/cases/{case_id}/restore", headers=u1_h, json={"version": 2}
            ).status_code
            == 403
        )

        # Supervisor restores with stale version -> 409
        assert (
            client.post(
                f"/api/cases/{case_id}/restore", headers=sup1_h, json={"version": 1}
            ).status_code
            == 409
        )

        # Supervisor restores with version 2 -> 200, clears dismissal -> notification reactivates!
        restored = client.post(
            f"/api/cases/{case_id}/restore", headers=sup1_h, json={"version": 2}
        )
        assert restored.status_code == 200
        assert restored.json()["archived"] is False
        assert restored.json()["version"] == 3
        u1_notifs = client.get("/api/notifications", headers=u1_h).json()
        assert [n["case_id"] for n in u1_notifs] == [case_id]

        # Reassign case from u1 to u2, then archive it as u2
        reassigned = client.patch(
            f"/api/cases/{case_id}",
            headers=admin_h,
            json={"version": 3, "assigned_to": ids["u2"]},
        )
        assert reassigned.status_code == 200
        assert (
            client.post(
                f"/api/cases/{case_id}/archive", headers=u2_h, json={"version": 4}
            ).status_code
            == 200
        )

        # u1 (past assignee) sees archived case read-only via GET /api/cases?archived=true
        u1_arc = client.get("/api/cases?archived=true", headers=u1_h).json()
        assert u1_arc["total"] == 1
        assert u1_arc["items"][0]["id"] == case_id
        assert u1_arc["items"][0]["is_readonly_archive"] is True

        # sup1 (past assignee's supervisor, no longer current team) sees it read-only and gets 403 on restore!
        sup1_arc = client.get("/api/cases?archived=true", headers=sup1_h).json()
        assert sup1_arc["total"] == 1
        assert sup1_arc["items"][0]["is_readonly_archive"] is True
        assert (
            client.post(
                f"/api/cases/{case_id}/restore", headers=sup1_h, json={"version": 5}
            ).status_code
            == 403
        )


class TestSpec009EditHistoryAndAdminAuditLog:
    def test_case_history_extra_key_diff_pesel_redaction_and_admin_audit_log(
        self, batch1_env
    ):
        client, _, ids = batch1_env
        admin_h = _login(client, "admin@b1.local", "AdminPass123!")
        u1_h = _login(client, "u1@b1.local", "UserPass1234!")
        u2_h = _login(client, "u2@b1.local", "UserPass1234!")

        created = client.post(
            "/api/cases",
            headers=admin_h,
            json={
                "case_number": "HIS-1",
                "title": "Sprawa z historią",
                "client_name": "Anna Nowak",
                "assigned_to": ids["u1"],
                "extra_fields": {"APROBANT": "Kowalska", "Pesel": "90010112345"},
            },
        )
        case_id = created.json()["id"]

        # Edit APROBANT and Pesel + change deadline with reason
        patch_res = client.patch(
            f"/api/cases/{case_id}",
            headers=admin_h,
            json={
                "version": 1,
                "deadline": "2027-03-10",
                "reason": "Korekta z pisma",
                "extra_fields": {"APROBANT": "Nowak", "Pesel": "99020254321"},
            },
        )
        assert patch_res.status_code == 200

        # Out-of-scope user gets 404 on history
        assert client.get(f"/api/cases/{case_id}/history", headers=u2_h).status_code == 404

        history = client.get(f"/api/cases/{case_id}/history", headers=u1_h).json()
        by_field = {h["field_name"]: h for h in history}
        assert "created" in by_field
        assert by_field["deadline"]["new_value"] == "2027-03-10"
        assert by_field["deadline"]["reason"] == "Korekta z pisma"
        assert by_field["extra:APROBANT"]["old_value"] == "Kowalska"
        assert by_field["extra:APROBANT"]["new_value"] == "Nowak"
        assert by_field["extra:Pesel"]["old_value"] == "[REDACTED]"
        assert by_field["extra:Pesel"]["new_value"] == "[REDACTED]"

        # Admin audit log: non-admin -> 403
        assert client.get("/api/admin/audit-log", headers=u1_h).status_code == 403

        # Admin updates u2 role & active status -> granular audit rows logged
        assert (
            client.patch(
                f"/api/admin/users/{ids['u2']}",
                headers=admin_h,
                json={"role": "supervisor", "is_active": False},
            ).status_code
            == 200
        )
        audit = client.get("/api/admin/audit-log", headers=admin_h).json()
        actions = {item["action"] for item in audit["items"]}
        assert "role_changed" in actions
        assert "user_deactivated" in actions

        filtered = client.get(
            "/api/admin/audit-log?action=role_changed", headers=admin_h
        ).json()
        assert filtered["total"] >= 1
        assert all(i["action"] == "role_changed" for i in filtered["items"])


class TestSpec010CaseAndPersonNotes:
    def test_case_notes_person_notes_archived_guard_and_delete_permissions(
        self, batch1_env
    ):
        client, _, ids = batch1_env
        admin_h = _login(client, "admin@b1.local", "AdminPass123!")
        sup1_h = _login(client, "sup1@b1.local", "SuperPass123!")
        u1_h = _login(client, "u1@b1.local", "UserPass1234!")
        u2_h = _login(client, "u2@b1.local", "UserPass1234!")

        case_id = client.post(
            "/api/cases",
            headers=admin_h,
            json={
                "title": "Sprawa z notatkami",
                "client_name": "Marek Test",
                "assigned_to": ids["u1"],
            },
        ).json()["id"]

        # Create case note as sup1 tagging u1
        n1 = client.post(
            f"/api/cases/{case_id}/notes",
            headers=sup1_h,
            json={"content": "Sprawdź załącznik nr 2", "subject_user_id": ids["u1"]},
        )
        assert n1.status_code == 201
        note_id = n1.json()["id"]
        assert n1.json()["subject_email"] == "u1@b1.local"

        # Empty note -> 400
        assert (
            client.post(
                f"/api/cases/{case_id}/notes", headers=u1_h, json={"content": "   "}
            ).status_code
            == 400
        )

        # u1 can read notes, cannot delete sup1's note -> 403
        assert len(client.get(f"/api/cases/{case_id}/notes", headers=u1_h).json()) == 1
        assert client.delete(f"/api/notes/{note_id}", headers=u1_h).status_code == 403
        # u2 (out of scope) -> 404
        assert client.delete(f"/api/notes/{note_id}", headers=u2_h).status_code == 404

        # Archive case -> adding new note returns 400, but author/admin can still delete existing note!
        assert (
            client.post(
                f"/api/cases/{case_id}/archive", headers=u1_h, json={"version": 1}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/cases/{case_id}/notes",
                headers=u1_h,
                json={"content": "Notatka na archiwum"},
            ).status_code
            == 400
        )
        assert client.delete(f"/api/notes/{note_id}", headers=admin_h).status_code == 204

        # Person-only notes ("notatka do osoby")
        pn = client.post(
            f"/api/users/{ids['u1']}/notes",
            headers=sup1_h,
            json={"content": "Urlop od poniedziałku — priorytet"},
        )
        assert pn.status_code == 201
        assert pn.json()["case_id"] is None
        assert pn.json()["subject_user_id"] == ids["u1"]

        # u1 sees own person notes; u2 gets 404
        assert len(client.get(f"/api/users/{ids['u1']}/notes", headers=u1_h).json()) == 1
        assert client.get(f"/api/users/{ids['u1']}/notes", headers=u2_h).status_code == 404
