from collections.abc import Generator
from datetime import date, datetime, timezone
import io
import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from main import app
from models import Case, User
from security import hash_password

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _make_xlsx(rows: list[list[object]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


@pytest.fixture()
def import_env(tmp_path) -> Generator[tuple[TestClient, sessionmaker[Session], dict[str, int]], None, None]:
    db_file = tmp_path / "import_test.db"
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
            email="admin@imp.local",
            hashed_password=hash_password("AdminPass123!"),
            is_active=True,
            role="admin",
            supervisor_id=None,
            must_change_password=False,
        )
        sup = User(
            email="sup@imp.local",
            hashed_password=hash_password("SuperPass123!"),
            is_active=True,
            role="supervisor",
            supervisor_id=None,
            must_change_password=False,
        )
        db.add_all([admin, sup])
        db.flush()

        user = User(
            email="user@imp.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=True,
            role="user",
            supervisor_id=sup.id,
            must_change_password=False,
        )
        inactive_user = User(
            email="inactive@imp.local",
            hashed_password=hash_password("UserPass1234!"),
            is_active=False,
            role="user",
            supervisor_id=sup.id,
            must_change_password=False,
        )
        db.add_all([user, inactive_user])
        db.flush()

        now = datetime.now(timezone.utc)
        existing_case = Case(
            case_number="51139292",
            title="Istniejąca sprawa",
            client_name="Jan Kowalski",
            assigned_to=user.id,
            deadline=date(2027, 1, 15),
            date_filed=date(2026, 11, 1),
            status="open",
            archived=False,
            version=1,
            extra_fields={"APROBANT": "Kowalska"},
            created_at=now,
            updated_at=now,
        )
        db.add(existing_case)
        db.commit()

        ids = {
            "admin": admin.id,
            "sup": sup.id,
            "user": user.id,
            "inactive": inactive_user.id,
            "existing_case": existing_case.id,
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


class TestUploadValidationAndLimits:
    def test_upload_role_mime_extension_size_and_5_copy_limit(self, import_env):
        client, _, ids = import_env
        admin_h = _login(client, "admin@imp.local", "AdminPass123!")
        user_h = _login(client, "user@imp.local", "UserPass1234!")

        valid_bytes = _make_xlsx([
            ["Nr sprawy", "Tytuł", "Klient", "Przypisany"],
            ["NEW-1", "Test", "Klient A", "user@imp.local"],
        ])

        # Non-admin upload -> 403
        res_403 = client.post(
            "/api/import/copies/upload",
            headers=user_h,
            files={"file": ("test.xlsx", valid_bytes, XLSX_MIME)},
        )
        assert res_403.status_code == 403

        # Wrong MIME -> 400
        res_mime = client.post(
            "/api/import/copies/upload",
            headers=admin_h,
            files={"file": ("test.xlsx", valid_bytes, "text/plain")},
        )
        assert res_mime.status_code == 400

        # Wrong extension -> 400
        res_ext = client.post(
            "/api/import/copies/upload",
            headers=admin_h,
            files={"file": ("test.csv", valid_bytes, XLSX_MIME)},
        )
        assert res_ext.status_code == 400

        # > 10 MB -> 413
        oversized = b"x" * (10 * 1024 * 1024 + 1)
        res_413 = client.post(
            "/api/import/copies/upload",
            headers=admin_h,
            files={"file": ("big.xlsx", oversized, XLSX_MIME)},
        )
        assert res_413.status_code == 413

        # Create 5 copies -> 201, 6th -> 409
        for idx in range(5):
            r = client.post(
                "/api/import/copies/upload",
                headers=admin_h,
                data={"default_assigned_to": str(ids["user"])},
                files={"file": (f"f{idx}.xlsx", valid_bytes, XLSX_MIME)},
            )
            assert r.status_code == 201
        sixth = client.post(
            "/api/import/copies/upload",
            headers=admin_h,
            files={"file": ("f6.xlsx", valid_bytes, XLSX_MIME)},
        )
        assert sixth.status_code == 409


class TestRealZusFormatAndCommitFlow:
    def test_zus_format_epwd_free_text_deadline_conflict_and_commit(self, import_env):
        client, SessionLocal, ids = import_env
        admin_h = _login(client, "admin@imp.local", "AdminPass123!")

        zus_bytes = _make_xlsx([
            [
                "DATA WPŁYWU EPWD",
                "DATA OPRACOWANIA",
                "DANE",
                "APROBANT",
                "Numer E2",
                "OFE",
                "Status",
                "INNE",
                "inne",
                "termin realizacji ",
            ],
            # Row 2: matches existing DB case_number 51139292 -> conflict!
            [
                "14.05.2026-ERN",
                "przekazane do WOL",
                "Jan Kowalski",
                "Lewandowska",
                51139292,
                "Tak",
                None,
                "Uwaga 1",
                "Uwaga 2",
                "wyjaśnienia SP ZOZ",
            ],
            # Row 3: pure-text EPWD + valid Polish deadline -> new case!
            [
                "z urzędu - EDUK",
                None,
                "Anna Nowak",
                "Nowakowski",
                99887766,
                None,
                None,
                None,
                None,
                "20.06.2026",
            ],
            # Row 4: broken date-like deadline -> blocking error!
            [
                "15.05.2026-ERN",
                None,
                "Marek Błąd",
                None,
                11223344,
                None,
                None,
                None,
                None,
                "32.13.2026",
            ],
        ])

        up = client.post(
            "/api/import/copies/upload",
            headers=admin_h,
            data={"default_assigned_to": str(ids["inactive"])},
            files={"file": ("Stan Sprawy.xlsx", zus_bytes, XLSX_MIME)},
        )
        assert up.status_code == 201, up.text
        copy = up.json()
        copy_id = copy["id"]
        assert copy["row_count"] == 3
        assert copy["error_count"] == 1
        assert copy["conflict_count"] == 1

        r2, r3, r4 = copy["rows"]
        # Row 2: EPWD date extracted, title auto-built, free-text deadline preserved with warning, DB conflict flagged
        assert r2["date_filed"] == "2026-05-14"
        assert r2["title"] == "ERN – Jan Kowalski"
        assert r2["deadline"] is None
        assert len(r2["warnings"]) == 1
        assert r2["extra_columns"]["termin realizacji"] == "wyjaśnienia SP ZOZ"
        assert r2["extra_columns"]["INNE"] == "Uwaga 1"
        assert r2["extra_columns"]["inne"] == "Uwaga 2"
        assert r2["assigned_to_email"] == "inactive@imp.local"
        assert r2["conflict"] is True
        assert r2["case_id"] == ids["existing_case"]

        # Row 3: pure text EPWD -> date_filed None, no error, Polish deadline parsed
        assert r3["date_filed"] is None
        assert r3["deadline"] == "2026-06-20"
        assert r3["errors"] == []

        # Row 4: malformed date -> blocking error
        assert len(r4["errors"]) == 1

        # Commit must fail with 400 while error + unresolved conflict exist
        assert (
            client.post(f"/api/import/copies/{copy_id}/commit", headers=admin_h).status_code
            == 400
        )

        # Fix row 4 date & resolve row 2 conflict as update_existing
        patched = client.patch(
            f"/api/import/copies/{copy_id}",
            headers=admin_h,
            json={
                "rows": [
                    {"row_index": r2["row_index"], "resolution": "update_existing"},
                    {"row_index": r4["row_index"], "deadline": "2026-07-01"},
                ]
            },
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["error_count"] == 0
        assert patched.json()["conflict_count"] == 0

        # Commit succeeds: 2 created (r3, r4), 1 updated (r2)
        commit_res = client.post(f"/api/import/copies/{copy_id}/commit", headers=admin_h)
        assert commit_res.status_code == 200, commit_res.text
        summary = commit_res.json()
        assert summary["created"] == 2
        assert summary["updated"] == 1
        assert summary["skipped"] == 0
        assert summary["conflicts"] == []
        assert summary["errors"] == []

        # Verify DB updated existing case version to 2
        with SessionLocal() as db:
            updated_case = db.scalar(select(Case).where(Case.id == ids["existing_case"]))
            assert updated_case is not None
            assert updated_case.version == 2
            assert updated_case.assigned_to == ids["inactive"]

        # Copy remains downloadable as valid .xlsx after commit
        dl = client.get(f"/api/import/copies/{copy_id}/download", headers=admin_h)
        assert dl.status_code == 200
        assert "attachment;" in dl.headers["content-disposition"]
        wb = openpyxl.load_workbook(io.BytesIO(dl.content))
        assert wb.active is not None
        assert wb.active.max_row == 4  # header + 3 rows


class TestSnapshotRoleProtectionAndVersionConflict:
    def test_snapshot_non_admin_date_403_cross_user_404_and_stale_commit_conflict(
        self, import_env
    ):
        client, _, ids = import_env
        user_h = _login(client, "user@imp.local", "UserPass1234!")
        admin_h = _login(client, "admin@imp.local", "AdminPass123!")

        snap = client.post("/api/import/copies/from-cases", headers=user_h)
        assert snap.status_code == 201
        copy_id = snap.json()["id"]
        row_idx = snap.json()["rows"][0]["row_index"]

        # Another user cannot read or delete this copy -> 404
        assert client.get(f"/api/import/copies/{copy_id}", headers=admin_h).status_code == 404

        # Non-admin editing deadline in copy -> 403
        assert (
            client.patch(
                f"/api/import/copies/{copy_id}",
                headers=user_h,
                json={"rows": [{"row_index": row_idx, "deadline": "2028-01-01"}]},
            ).status_code
            == 403
        )

        # User edits title in copy -> 200
        assert (
            client.patch(
                f"/api/import/copies/{copy_id}",
                headers=user_h,
                json={"rows": [{"row_index": row_idx, "title": "Zmieniony w kopii"}]},
            ).status_code
            == 200
        )

        # Meanwhile, admin updates live case -> live version becomes 2
        assert (
            client.patch(
                f"/api/cases/{ids['existing_case']}",
                headers=admin_h,
                json={"version": 1, "title": "Zmiana admina na żywo"},
            ).status_code
            == 200
        )

        # User commits stale copy -> per-row conflict reported, zero silent overwrite!
        commit_res = client.post(f"/api/import/copies/{copy_id}/commit", headers=user_h)
        assert commit_res.status_code == 200
        body = commit_res.json()
        assert body["updated"] == 0
        assert len(body["conflicts"]) == 1
        assert body["conflicts"][0]["case_id"] == ids["existing_case"]

    def test_supervisor_can_upload_and_commit_for_own_team(self, import_env):
        client, _, ids = import_env
        sup_h = _login(client, "sup@imp.local", "SuperPass123!")

        zus_bytes = _make_xlsx([
            ["DATA WPŁYWU EPWD", "DANE", "Numer E2", "termin realizacji "],
            ["14.05.2026-ERN", "Katarzyna Test", 77665544, "25.06.2026"],
        ])

        up = client.post(
            "/api/import/copies/upload",
            headers=sup_h,
            data={"default_assigned_to": str(ids["user"])},
            files={"file": ("team.xlsx", zus_bytes, XLSX_MIME)},
        )
        assert up.status_code == 201, up.text
        copy_id = up.json()["id"]

        # Supervisor still cannot manually edit deadline cell -> 403
        assert (
            client.patch(
                f"/api/import/copies/{copy_id}",
                headers=sup_h,
                json={"rows": [{"row_index": 2, "deadline": "2028-01-01"}]},
            ).status_code
            == 403
        )

        # Supervisor commits uploaded file -> 200, 1 created with imported dates preserved
        commit_res = client.post(f"/api/import/copies/{copy_id}/commit", headers=sup_h)
        assert commit_res.status_code == 200, commit_res.text
        assert commit_res.json()["created"] == 1
