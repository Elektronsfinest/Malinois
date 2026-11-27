from datetime import date, datetime, timedelta, timezone
import gzip
from io import BytesIO
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
import openpyxl
from sqlalchemy import select
from database import SessionLocal
from main import app
from models import AdminAuditLog, BackupLog, Case, CaseAssignmentHistory, CaseEditLog, CaseNote, User
from security import hash_password
from services.backups import get_backup_dir, prune_old_backups

client = TestClient(app)
WARSAW_TZ = ZoneInfo("Europe/Warsaw")


def _today_warsaw() -> date:
    return datetime.now(WARSAW_TZ).date()


def _login(email: str, password: str = "Secret123!") -> str:
    res = client.post("/api/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ensure_user(
    email: str,
    *,
    role: str = "user",
    supervisor_email: str | None = None,
    is_active: bool = True,
) -> int:
    with SessionLocal() as db:
        sup_id = None
        if supervisor_email:
            sup = db.scalar(select(User).where(User.email == supervisor_email))
            assert sup is not None
            sup_id = sup.id
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password("Secret123!"),
                role=role,
                supervisor_id=sup_id,
                is_active=is_active,
                must_change_password=False,
            )
            db.add(user)
        else:
            user.role = role
            user.supervisor_id = sup_id
            user.is_active = is_active
        db.commit()
        db.refresh(user)
        return user.id


def _create_case_as_admin(
    admin_token: str,
    *,
    title: str,
    client_name: str,
    assigned_to: int,
    deadline: date | None = None,
    status_val: str = "open",
    case_number: str | None = None,
) -> dict:
    payload = {
        "title": title,
        "client_name": client_name,
        "assigned_to": assigned_to,
        "deadline": deadline.isoformat() if deadline else None,
        "status": status_val,
        "case_number": case_number,
    }
    res = client.post("/api/cases", json=payload, headers=_headers(admin_token))
    assert res.status_code == 201, res.text
    return res.json()


def test_search_and_filtering_spec_013():
    admin_token = _login("admin@example.com")
    sup_token = _login("sup@example.com")
    user_token = _login("trainee@example.com")

    with SessionLocal() as db:
        trainee = db.scalar(select(User).where(User.email == "trainee@example.com"))
        sup = db.scalar(select(User).where(User.email == "sup@example.com"))
        assert trainee is not None and sup is not None
        trainee_id, sup_id = trainee.id, sup.id

    outsider_id = _ensure_user("outsider_013@example.com", role="user", supervisor_email=None)

    today = _today_warsaw()
    suffix = datetime.now(timezone.utc).strftime("%H%M%S%f")
    c_overdue = _create_case_as_admin(
        admin_token,
        title=f"Zalegla {suffix}",
        client_name=f"Klient Overdue {suffix}",
        assigned_to=trainee_id,
        deadline=today - timedelta(days=2),
        case_number=f"SRCH-OV-{suffix}",
    )
    c_today = _create_case_as_admin(
        admin_token,
        title=f"Dzisiaj {suffix}",
        client_name=f"Klient Today {suffix}",
        assigned_to=trainee_id,
        deadline=today,
        case_number=f"SRCH-TD-{suffix}",
    )
    c_closed = _create_case_as_admin(
        admin_token,
        title=f"Zamknieta {suffix}",
        client_name=f"Klient Closed {suffix}",
        assigned_to=sup_id,
        deadline=today + timedelta(days=3),
        status_val="closed",
        case_number=f"SRCH-CL-{suffix}",
    )

    # q search matches case_number / title / client_name case-insensitively
    r_q = client.get(
        f"/api/cases?q=srch-ov-{suffix.lower()}", headers=_headers(user_token)
    )
    assert r_q.status_code == 200
    assert [i["id"] for i in r_q.json()["items"]] == [c_overdue["id"]]

    # overdue=true: strictly < today (today's deadline is NOT overdue)
    r_ov = client.get(
        f"/api/cases?q={suffix}&overdue=true", headers=_headers(user_token)
    )
    assert r_ov.status_code == 200
    assert [i["id"] for i in r_ov.json()["items"]] == [c_overdue["id"]]

    # due_soon=true: today <= deadline <= today + threshold
    r_ds = client.get(
        f"/api/cases?q={suffix}&due_soon=true", headers=_headers(user_token)
    )
    assert r_ds.status_code == 200
    assert [i["id"] for i in r_ds.json()["items"]] == [c_today["id"]]

    # status=closed + sort=deadline_desc
    r_cl = client.get(
        f"/api/cases?q={suffix}&status=closed&sort=deadline_desc",
        headers=_headers(sup_token),
    )
    assert r_cl.status_code == 200
    assert [i["id"] for i in r_cl.json()["items"]] == [c_closed["id"]]

    # Role scoping on assigned_to filter
    assert (
        client.get(f"/api/cases?assigned_to={sup_id}", headers=_headers(user_token)).status_code
        == 403
    )
    assert (
        client.get(f"/api/cases?assigned_to={outsider_id}", headers=_headers(sup_token)).status_code
        == 403
    )
    assert (
        client.get(f"/api/cases?assigned_to={trainee_id}", headers=_headers(sup_token)).status_code
        == 200
    )

    # Invalid sort / invalid date -> 400
    assert (
        client.get("/api/cases?sort=invalid_sort", headers=_headers(admin_token)).status_code
        == 400
    )
    assert (
        client.get("/api/cases?deadline_from=not-a-date", headers=_headers(admin_token)).status_code
        == 400
    )


def test_dashboard_summary_spec_014():
    admin_token = _login("admin@example.com")
    sup_token = _login("sup@example.com")
    user_token = _login("trainee@example.com")

    r_user = client.get("/api/dashboard/summary", headers=_headers(user_token))
    assert r_user.status_code == 200
    du = r_user.json()
    assert du["team_summary"] is None
    assert du["total_cases"] is None
    assert isinstance(du["open_cases"], int)
    assert isinstance(du["overdue_cases"], int)
    assert isinstance(du["due_soon"], int)
    assert isinstance(du["closed_this_month"], int)

    r_sup = client.get("/api/dashboard/summary", headers=_headers(sup_token))
    assert r_sup.status_code == 200
    ds = r_sup.json()
    assert isinstance(ds["team_summary"], list)
    sup_emails = {m["email"] for m in ds["team_summary"]}
    assert "sup@example.com" in sup_emails
    assert "trainee@example.com" in sup_emails

    r_adm = client.get("/api/dashboard/summary", headers=_headers(admin_token))
    assert r_adm.status_code == 200
    da = r_adm.json()
    assert isinstance(da["total_cases"], int)
    assert isinstance(da["team_summary"], list)
    assert da["notification_threshold_days"] >= 1


def test_bulk_operations_spec_015():
    admin_token = _login("admin@example.com")
    sup_token = _login("sup@example.com")
    user_token = _login("trainee@example.com")

    with SessionLocal() as db:
        trainee = db.scalar(select(User).where(User.email == "trainee@example.com"))
        sup = db.scalar(select(User).where(User.email == "sup@example.com"))
        assert trainee is not None and sup is not None
        trainee_id, sup_id = trainee.id, sup.id

    c1 = _create_case_as_admin(
        admin_token, title="Bulk 1", client_name="Klient B1", assigned_to=trainee_id
    )
    c2 = _create_case_as_admin(
        admin_token, title="Bulk 2", client_name="Klient B2", assigned_to=trainee_id
    )
    c_sup = _create_case_as_admin(
        admin_token, title="Bulk Sup", client_name="Klient BS", assigned_to=sup_id
    )

    # 400 on unknown action / empty list
    assert (
        client.post(
            "/api/cases/bulk",
            json={"items": [], "action": "archive"},
            headers=_headers(user_token),
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/cases/bulk",
            json={"items": [{"id": c1["id"], "version": c1["version"]}], "action": "delete_all"},
            headers=_headers(user_token),
        ).status_code
        == 400
    )

    # 404 when any item is outside user's scope (atomic rollback)
    r_oos = client.post(
        "/api/cases/bulk",
        json={
            "items": [
                {"id": c1["id"], "version": c1["version"]},
                {"id": c_sup["id"], "version": c_sup["version"]},
            ],
            "action": "set_status",
            "params": {"status": "closed"},
        },
        headers=_headers(user_token),
    )
    assert r_oos.status_code == 404

    # 409 on stale version (atomic rollback)
    r_conflict = client.post(
        "/api/cases/bulk",
        json={
            "items": [
                {"id": c1["id"], "version": c1["version"]},
                {"id": c2["id"], "version": 999},
            ],
            "action": "set_status",
            "params": {"status": "closed"},
        },
        headers=_headers(user_token),
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json()["conflicts"][0]["case_id"] == c2["id"]

    # Valid bulk set_status -> 200
    r_ok = client.post(
        "/api/cases/bulk",
        json={
            "items": [
                {"id": c1["id"], "version": c1["version"]},
                {"id": c2["id"], "version": c2["version"]},
            ],
            "action": "set_status",
            "params": {"status": "closed"},
        },
        headers=_headers(user_token),
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["affected_count"] == 2

    # Archive both (version is now +1)
    r_arch = client.post(
        "/api/cases/bulk",
        json={
            "items": [
                {"id": c1["id"], "version": c1["version"] + 1},
                {"id": c2["id"], "version": c2["version"] + 1},
            ],
            "action": "archive",
        },
        headers=_headers(user_token),
    )
    assert r_arch.status_code == 200

    # Regular user cannot bulk restore -> 403
    r_forbid = client.post(
        "/api/cases/bulk",
        json={
            "items": [{"id": c1["id"], "version": c1["version"] + 2}],
            "action": "restore",
        },
        headers=_headers(user_token),
    )
    assert r_forbid.status_code == 403

    # Supervisor can bulk restore -> 200
    r_rest = client.post(
        "/api/cases/bulk",
        json={
            "items": [{"id": c1["id"], "version": c1["version"] + 2}],
            "action": "restore",
        },
        headers=_headers(sup_token),
    )
    assert r_rest.status_code == 200


def test_case_reassignment_spec_016():
    admin_token = _login("admin@example.com")
    sup_token = _login("sup@example.com")
    user_token = _login("trainee@example.com")

    with SessionLocal() as db:
        trainee = db.scalar(select(User).where(User.email == "trainee@example.com"))
        sup = db.scalar(select(User).where(User.email == "sup@example.com"))
        assert trainee is not None and sup is not None
        trainee_id, sup_id = trainee.id, sup.id

    outsider_id = _ensure_user("outsider_016@example.com", role="user", supervisor_email=None)
    inactive_id = _ensure_user(
        "inactive_016@example.com", role="user", supervisor_email="sup@example.com", is_active=False
    )

    c = _create_case_as_admin(
        admin_token, title="Reassign Case", client_name="Klient R", assigned_to=trainee_id
    )

    # Regular user -> 403
    assert (
        client.post(
            "/api/cases/reassign",
            json={
                "items": [{"id": c["id"], "version": c["version"]}],
                "new_assigned_to": sup_id,
            },
            headers=_headers(user_token),
        ).status_code
        == 403
    )

    # Inactive target -> 400
    assert (
        client.post(
            "/api/cases/reassign",
            json={
                "items": [{"id": c["id"], "version": c["version"]}],
                "new_assigned_to": inactive_id,
            },
            headers=_headers(sup_token),
        ).status_code
        == 400
    )

    # Supervisor reassigning to out-of-team target -> 403
    assert (
        client.post(
            "/api/cases/reassign",
            json={
                "items": [{"id": c["id"], "version": c["version"]}],
                "new_assigned_to": outsider_id,
            },
            headers=_headers(sup_token),
        ).status_code
        == 403
    )

    # Stale version -> 409
    assert (
        client.post(
            "/api/cases/reassign",
            json={
                "items": [{"id": c["id"], "version": 999}],
                "new_assigned_to": sup_id,
            },
            headers=_headers(sup_token),
        ).status_code
        == 409
    )

    # Valid supervisor reassignment with reason -> 200 + history + edit_log + automated note
    r_ok = client.post(
        "/api/cases/reassign",
        json={
            "items": [{"id": c["id"], "version": c["version"]}],
            "new_assigned_to": sup_id,
            "reason": "Zastępstwo na czas urlopu",
        },
        headers=_headers(sup_token),
    )
    assert r_ok.status_code == 200, r_ok.text
    assert r_ok.json()["reassigned_count"] == 1
    assert r_ok.json()["new_assigned_to_email"] == "sup@example.com"

    with SessionLocal() as db:
        hist = db.scalars(
            select(CaseAssignmentHistory).where(CaseAssignmentHistory.case_id == c["id"])
        ).all()
        assert len(hist) >= 2
        edit = db.scalar(
            select(CaseEditLog).where(
                CaseEditLog.case_id == c["id"],
                CaseEditLog.field_name == "assigned_to",
            )
        )
        assert edit is not None
        assert edit.reason == "Zastępstwo na czas urlopu"
        note = db.scalar(
            select(CaseNote).where(CaseNote.case_id == c["id"])
        )
        assert note is not None
        assert "Przepisano sprawę na sup@example.com" in note.content


def test_automated_backups_and_pre_import_spec_017():
    admin_token = _login("admin@example.com")
    sup_token = _login("sup@example.com")
    user_token = _login("trainee@example.com")

    # Non-admins -> 403
    assert client.get("/api/admin/backups", headers=_headers(user_token)).status_code == 403
    assert client.post("/api/admin/backups", headers=_headers(sup_token)).status_code == 403

    # Manual backup -> 201 + valid gzip file on disk
    r_create = client.post("/api/admin/backups", headers=_headers(admin_token))
    assert r_create.status_code == 201, r_create.text
    b = r_create.json()
    assert b["backup_type"] == "manual"
    assert b["size_bytes"] > 0
    backup_path = get_backup_dir() / b["filename"]
    assert backup_path.is_file()

    # List includes created backup
    r_list = client.get("/api/admin/backups", headers=_headers(admin_token))
    assert r_list.status_code == 200
    assert any(item["filename"] == b["filename"] for item in r_list.json())

    # Download: path traversal -> 400
    assert (
        client.post(
            "/api/admin/backups/..%2Fdev.db/download",
            json={"password": "Secret123!"},
            headers=_headers(admin_token),
        ).status_code
        == 400
    )

    # Download: wrong password -> 401
    assert (
        client.post(
            f"/api/admin/backups/{b['filename']}/download",
            json={"password": "WrongPassword1!"},
            headers=_headers(admin_token),
        ).status_code
        == 401
    )

    # Download: valid password -> 200 gzip stream + audit log entry
    r_dl = client.post(
        f"/api/admin/backups/{b['filename']}/download",
        json={"password": "Secret123!"},
        headers=_headers(admin_token),
    )
    assert r_dl.status_code == 200
    assert r_dl.headers["content-type"] == "application/gzip"
    # Verify it is valid gzip
    decompressed = gzip.decompress(r_dl.content)
    assert len(decompressed) > 0

    with SessionLocal() as db:
        audit_dl = db.scalar(
            select(AdminAuditLog)
            .where(AdminAuditLog.action == "backup_downloaded")
            .order_by(AdminAuditLog.id.desc())
        )
        assert audit_dl is not None
        assert (audit_dl.details or {}).get("filename") == b["filename"]

    # Pre-import backup hook on Excel commit
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Numer sprawy", "Tytuł", "Klient", "Przypisany", "Termin", "Status"])
    ws.append([
        f"BKP-IMP-{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
        "Sprawa z importu",
        "Klient Import",
        "trainee@example.com",
        "2027-06-15",
        "open",
    ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    r_up = client.post(
        "/api/import/copies/upload",
        files={
            "file": (
                "pre_import_test.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=_headers(admin_token),
    )
    assert r_up.status_code == 201, r_up.text
    copy_id = r_up.json()["id"]
    r_commit = client.post(
        f"/api/import/copies/{copy_id}/commit", headers=_headers(admin_token)
    )
    assert r_commit.status_code == 200, r_commit.text

    with SessionLocal() as db:
        pre_imp = db.scalar(
            select(BackupLog)
            .where(BackupLog.backup_type == "pre_import")
            .order_by(BackupLog.id.desc())
        )
        assert pre_imp is not None

        # Retention pruning: age one backup log entry to 20 days old and prune
        pre_imp.created_at = datetime.now(timezone.utc) - timedelta(days=20)
        old_file = get_backup_dir() / pre_imp.filename
        db.commit()
        cases_before = len(db.scalars(select(Case.id)).all())
        removed = prune_old_backups(db, retention_days=14)
        assert removed >= 1
        assert not old_file.exists()
        assert len(db.scalars(select(Case.id)).all()) == cases_before
