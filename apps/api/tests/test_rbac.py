from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from main import app
from models import User
from security import hash_password


@pytest.fixture()
def rbac_db(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    db_file = tmp_path / "rbac_test.db"
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
            email="admin@test.local",
            hashed_password=hash_password("AdminPass123!"),
            is_active=True,
            role="admin",
            supervisor_id=None,
            must_change_password=False,
        )
        supervisor = User(
            email="supervisor@test.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([admin, supervisor])
        db.flush()

        sub_user = User(
            email="user@test.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=supervisor.id,
            must_change_password=False,
        )
        db.add(sub_user)
        db.commit()

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app), TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()


def _login(client: TestClient, email: str, password: str) -> str:
    res = client.post("/api/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAuthExtendedPayloadAndMustChangePassword:
    def test_login_and_me_include_role_supervisor_and_must_change_password(self, rbac_db):
        client, _ = rbac_db
        login_res = client.post(
            "/api/login",
            json={"email": "user@test.local", "password": "UserPass1234!"},
        )
        assert login_res.status_code == 200
        body = login_res.json()
        assert body["user"]["role"] == "user"
        assert body["user"]["supervisor_id"] is not None
        assert body["user"]["must_change_password"] is False

        me_res = client.get("/api/me", headers=_auth_header(body["access_token"]))
        assert me_res.status_code == 200
        me = me_res.json()
        assert me["role"] == "user"
        assert me["supervisor_id"] == body["user"]["supervisor_id"]
        assert me["must_change_password"] is False

    def test_must_change_password_allows_me_but_blocks_other_endpoints_with_403(
        self, rbac_db
    ):
        client, _ = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")

        created = client.post(
            "/api/admin/users",
            headers=_auth_header(admin_token),
            json={
                "email": "newadmin@test.local",
                "password": "TempPassword1!",
                "role": "admin",
            },
        )
        assert created.status_code == 201
        assert created.json()["must_change_password"] is True

        new_token = _login(client, "newadmin@test.local", "TempPassword1!")

        # /api/me must still succeed so frontend can detect must_change_password
        me_res = client.get("/api/me", headers=_auth_header(new_token))
        assert me_res.status_code == 200
        assert me_res.json()["must_change_password"] is True

        # Protected endpoints must return 403 with code password_change_required
        blocked = client.get("/api/admin/users", headers=_auth_header(new_token))
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "password_change_required"


class TestRoleMatrixOnAdminEndpoints:
    def test_non_admin_and_unauthenticated_blocked_from_admin_users(self, rbac_db):
        client, _ = rbac_db
        sup_token = _login(client, "supervisor@test.local", "SuperPass123!")
        user_token = _login(client, "user@test.local", "UserPass1234!")

        assert client.get("/api/admin/users").status_code == 401
        assert (
            client.get("/api/admin/users", headers=_auth_header(sup_token)).status_code
            == 403
        )
        assert (
            client.get("/api/admin/users", headers=_auth_header(user_token)).status_code
            == 403
        )
        assert (
            client.post(
                "/api/admin/users",
                headers=_auth_header(sup_token),
                json={
                    "email": "x@test.local",
                    "password": "ValidPass123!",
                    "role": "user",
                },
            ).status_code
            == 403
        )
        assert (
            client.patch(
                "/api/admin/users/1",
                headers=_auth_header(user_token),
                json={"role": "admin"},
            ).status_code
            == 403
        )


class TestAdminUserCreationAndListing:
    def test_list_users_supports_role_supervisor_and_is_active_filters(self, rbac_db):
        client, _ = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")

        all_users = client.get(
            "/api/admin/users", headers=_auth_header(admin_token)
        ).json()
        assert len(all_users) == 3

        supervisors = client.get(
            "/api/admin/users?role=supervisor", headers=_auth_header(admin_token)
        ).json()
        assert len(supervisors) == 1
        sup_id = supervisors[0]["id"]

        subs = client.get(
            f"/api/admin/users?supervisor_id={sup_id}",
            headers=_auth_header(admin_token),
        ).json()
        assert [u["email"] for u in subs] == ["user@test.local"]

        inactive = client.get(
            "/api/admin/users?is_active=false", headers=_auth_header(admin_token)
        ).json()
        assert inactive == []

    def test_create_user_validation_and_admin_as_supervisor(self, rbac_db):
        client, _ = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")
        users = client.get("/api/admin/users", headers=_auth_header(admin_token)).json()
        admin_id = next(u["id"] for u in users if u["role"] == "admin")
        regular_id = next(u["id"] for u in users if u["role"] == "user")

        # Admin is allowed to supervise regular users
        ok = client.post(
            "/api/admin/users",
            headers=_auth_header(admin_token),
            json={
                "email": "under_admin@test.local",
                "password": "ValidPassword1!",
                "role": "user",
                "supervisor_id": admin_id,
            },
        )
        assert ok.status_code == 201
        assert ok.json()["supervisor_id"] == admin_id
        assert ok.json()["must_change_password"] is True

        # Duplicate email -> 400
        dup = client.post(
            "/api/admin/users",
            headers=_auth_header(admin_token),
            json={
                "email": "UNDER_ADMIN@test.local",
                "password": "ValidPassword1!",
                "role": "user",
            },
        )
        assert dup.status_code == 400

        # Weak password -> 400
        weak = client.post(
            "/api/admin/users",
            headers=_auth_header(admin_token),
            json={
                "email": "weak@test.local",
                "password": "short",
                "role": "user",
            },
        )
        assert weak.status_code == 400

        # Regular user cannot be supervisor -> 400
        bad_sup = client.post(
            "/api/admin/users",
            headers=_auth_header(admin_token),
            json={
                "email": "bad_sup@test.local",
                "password": "ValidPassword1!",
                "role": "user",
                "supervisor_id": regular_id,
            },
        )
        assert bad_sup.status_code == 400

        # Supervisor cannot have a supervisor -> 400
        nested = client.post(
            "/api/admin/users",
            headers=_auth_header(admin_token),
            json={
                "email": "nested@test.local",
                "password": "ValidPassword1!",
                "role": "supervisor",
                "supervisor_id": admin_id,
            },
        )
        assert nested.status_code == 400


class TestAdminUserUpdateHierarchyAndDeactivation:
    def test_self_lockout_and_last_admin_protection(self, rbac_db):
        client, _ = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")
        users = client.get("/api/admin/users", headers=_auth_header(admin_token)).json()
        admin_id = next(u["id"] for u in users if u["role"] == "admin")

        # Self-deactivation -> 400
        assert (
            client.patch(
                f"/api/admin/users/{admin_id}",
                headers=_auth_header(admin_token),
                json={"is_active": False},
            ).status_code
            == 400
        )

        # Self-demotion -> 400
        assert (
            client.patch(
                f"/api/admin/users/{admin_id}",
                headers=_auth_header(admin_token),
                json={"role": "supervisor"},
            ).status_code
            == 400
        )

    def test_promotion_auto_clears_supervisor_and_supervisor_to_admin_keeps_subordinates(
        self, rbac_db
    ):
        client, _ = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")
        users = client.get("/api/admin/users", headers=_auth_header(admin_token)).json()
        sup_id = next(u["id"] for u in users if u["role"] == "supervisor")
        user_id = next(u["id"] for u in users if u["role"] == "user")

        # Promoting supervisor -> admin preserves subordinates cleanly
        promoted_sup = client.patch(
            f"/api/admin/users/{sup_id}",
            headers=_auth_header(admin_token),
            json={"role": "admin"},
        )
        assert promoted_sup.status_code == 200
        assert promoted_sup.json()["role"] == "admin"

        refreshed_users = client.get(
            "/api/admin/users", headers=_auth_header(admin_token)
        ).json()
        sub = next(u for u in refreshed_users if u["id"] == user_id)
        assert sub["supervisor_id"] == sup_id

        # Promoting user -> supervisor auto-clears supervisor_id to null
        promoted_user = client.patch(
            f"/api/admin/users/{user_id}",
            headers=_auth_header(admin_token),
            json={"role": "supervisor"},
        )
        assert promoted_user.status_code == 200
        assert promoted_user.json()["role"] == "supervisor"
        assert promoted_user.json()["supervisor_id"] is None

    def test_demoting_or_deactivating_manager_with_subordinates_requires_reassignment(
        self, rbac_db
    ):
        client, SessionLocal = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")
        sup_token = _login(client, "supervisor@test.local", "SuperPass123!")
        users = client.get("/api/admin/users", headers=_auth_header(admin_token)).json()
        admin_id = next(u["id"] for u in users if u["role"] == "admin")
        sup_id = next(u["id"] for u in users if u["role"] == "supervisor")
        user_id = next(u["id"] for u in users if u["role"] == "user")

        # Demoting supervisor -> user without reassign_subordinates_to -> 409
        conflict_demote = client.patch(
            f"/api/admin/users/{sup_id}",
            headers=_auth_header(admin_token),
            json={"role": "user"},
        )
        assert conflict_demote.status_code == 409
        assert conflict_demote.json()["blocking_subordinate_ids"] == [user_id]
        assert conflict_demote.json()["blocking_case_ids"] == []

        # Deactivating supervisor without reassign_subordinates_to -> 409
        conflict_deact = client.patch(
            f"/api/admin/users/{sup_id}",
            headers=_auth_header(admin_token),
            json={"is_active": False},
        )
        assert conflict_deact.status_code == 409
        assert conflict_deact.json()["blocking_subordinate_ids"] == [user_id]

        # Deactivating WITH reassign_subordinates_to=admin_id -> 200 atomic
        ok = client.patch(
            f"/api/admin/users/{sup_id}",
            headers=_auth_header(admin_token),
            json={"is_active": False, "reassign_subordinates_to": admin_id},
        )
        assert ok.status_code == 200
        assert ok.json()["is_active"] is False

        # Subordinate is now assigned to admin_id
        with SessionLocal() as db:
            sub = db.scalar(select(User).where(User.id == user_id))
            assert sub is not None
            assert sub.supervisor_id == admin_id

        # Deactivated supervisor's existing JWT immediately returns 401
        assert client.get("/api/me", headers=_auth_header(sup_token)).status_code == 401

    def test_self_supervision_and_invalid_reassign_cases_to_rejected(self, rbac_db):
        client, _ = rbac_db
        admin_token = _login(client, "admin@test.local", "AdminPass123!")
        users = client.get("/api/admin/users", headers=_auth_header(admin_token)).json()
        user_id = next(u["id"] for u in users if u["role"] == "user")

        # Self-supervision -> 400
        assert (
            client.patch(
                f"/api/admin/users/{user_id}",
                headers=_auth_header(admin_token),
                json={"supervisor_id": user_id},
            ).status_code
            == 400
        )

        # Invalid reassign_cases_to -> 400
        assert (
            client.patch(
                f"/api/admin/users/{user_id}",
                headers=_auth_header(admin_token),
                json={"is_active": False, "reassign_cases_to": 9999},
            ).status_code
            == 400
        )
