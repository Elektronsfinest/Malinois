from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from main import app
from models import AdminAuditLog, LoginAuditLog, User
from security import hash_password, validate_password_policy


@pytest.fixture()
def batch2_env(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, int]], None, None]:
    db_file = tmp_path / "batch2_test.db"
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
            email="admin@b2.local",
            hashed_password=hash_password("AdminPass123!"),
            is_active=True,
            role="admin",
            supervisor_id=None,
            must_change_password=False,
        )
        user = User(
            email="user@b2.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([admin, user])
        db.commit()
        ids = {"admin": admin.id, "user": user.id}

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


class TestSpec007SecurityHeadersRateLimitAndLoginAudit:
    def test_security_headers_present_on_api_responses(self, batch2_env):
        client, _, _ = batch2_env
        res = client.get("/health")
        assert res.status_code == 200
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in res.headers["content-security-policy"]

    def test_login_rate_limit_429_and_failed_login_audit_log(self, batch2_env):
        client, SessionLocal, _ = batch2_env

        for _ in range(10):
            r = client.post(
                "/api/login",
                json={"email": "user@b2.local", "password": "WrongPassword!"},
            )
            assert r.status_code == 401

        # 11th request within 60s -> 429 Too Many Requests
        r11 = client.post(
            "/api/login",
            json={"email": "user@b2.local", "password": "UserPass1234!"},
        )
        assert r11.status_code == 429

        with SessionLocal() as db:
            logs = list(db.scalars(select(LoginAuditLog)).all())
            assert len(logs) == 10
            assert all(log.attempted_email == "user@b2.local" and not log.success for log in logs)


class TestSpec008UserSettingsAndPasswordChange:
    def test_admin_reset_password_forces_change_then_self_service_unlocks(self, batch2_env):
        client, SessionLocal, ids = batch2_env
        admin_h = _login(client, "admin@b2.local", "AdminPass123!")

        # Admin cannot self-reset -> 400
        assert (
            client.post(
                f"/api/admin/users/{ids['admin']}/reset-password", headers=admin_h
            ).status_code
            == 400
        )

        # Admin resets user password -> 200 with strong temporary password
        reset_res = client.post(
            f"/api/admin/users/{ids['user']}/reset-password", headers=admin_h
        )
        assert reset_res.status_code == 200
        temp_pwd = reset_res.json()["temporary_password"]
        validate_password_policy(temp_pwd)

        # Audit log recorded password_reset
        with SessionLocal() as db:
            audit_actions = [a.action for a in db.scalars(select(AdminAuditLog)).all()]
            assert "password_reset" in audit_actions

        # User logs in with temporary password -> must_change_password is True
        user_h = _login(client, "user@b2.local", temp_pwd)
        me = client.get("/api/me", headers=user_h).json()
        assert me["must_change_password"] is True

        # Protected endpoints blocked with 403 password_change_required
        blocked = client.get("/api/cases", headers=user_h)
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "password_change_required"

        # Weak password or same password rejected with 400
        assert (
            client.patch(
                "/api/me/password",
                headers=user_h,
                json={"current_password": temp_pwd, "new_password": "short"},
            ).status_code
            == 400
        )
        assert (
            client.patch(
                "/api/me/password",
                headers=user_h,
                json={"current_password": temp_pwd, "new_password": temp_pwd},
            ).status_code
            == 400
        )

        # Valid password change -> 204, clears must_change_password, existing JWT remains valid!
        changed = client.patch(
            "/api/me/password",
            headers=user_h,
            json={"current_password": temp_pwd, "new_password": "NewStrongPass2@#"},
        )
        assert changed.status_code == 204
        assert client.get("/api/me", headers=user_h).json()["must_change_password"] is False
        assert client.get("/api/cases", headers=user_h).status_code == 200

    def test_ui_settings_persistence_and_validation(self, batch2_env):
        client, _, _ = batch2_env
        user_h = _login(client, "user@b2.local", "UserPass1234!")

        updated = client.patch(
            "/api/me/settings",
            headers=user_h,
            json={"theme": "light", "font_size": "large", "high_contrast": True},
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "theme": "light",
            "font_size": "large",
            "high_contrast": True,
            "reduced_motion": None,
        }

        # Persists on GET /api/me
        me = client.get("/api/me", headers=user_h).json()
        assert me["ui_settings"]["theme"] == "light"
        assert me["ui_settings"]["font_size"] == "large"
        assert me["ui_settings"]["high_contrast"] is True

        # Unknown field rejected (422)
        bad = client.patch(
            "/api/me/settings",
            headers=user_h,
            json={"notifications_sound": True},
        )
        assert bad.status_code in (400, 422)


class TestSpec012AdminSettingsPropagation:
    def test_admin_settings_crud_validation_and_me_propagation(self, batch2_env):
        client, _, _ = batch2_env
        admin_h = _login(client, "admin@b2.local", "AdminPass123!")
        user_h = _login(client, "user@b2.local", "UserPass1234!")

        # Non-admin blocked -> 403
        assert client.get("/api/admin/settings", headers=user_h).status_code == 403
        assert (
            client.patch(
                "/api/admin/settings",
                headers=user_h,
                json={"notification_threshold_days": 14},
            ).status_code
            == 403
        )

        # Default is 7
        assert client.get("/api/admin/settings", headers=admin_h).json() == {
            "notification_threshold_days": 7
        }

        # Out-of-range -> 400
        assert (
            client.patch(
                "/api/admin/settings",
                headers=admin_h,
                json={"notification_threshold_days": 0},
            ).status_code
            == 400
        )
        assert (
            client.patch(
                "/api/admin/settings",
                headers=admin_h,
                json={"notification_threshold_days": 400},
            ).status_code
            == 400
        )

        # Update to 14 -> immediately reflected in /api/me for non-admin!
        ok = client.patch(
            "/api/admin/settings",
            headers=admin_h,
            json={"notification_threshold_days": 14},
        )
        assert ok.status_code == 200
        assert ok.json()["notification_threshold_days"] == 14
        assert client.get("/api/me", headers=user_h).json()["notification_threshold_days"] == 14
