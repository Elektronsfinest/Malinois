from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
import openpyxl
from sqlalchemy import select
from database import SessionLocal
from main import app
from models import User
from security import hash_password
from services.excel_adapter import build_xlsx_bytes, parse_date_value, parse_excel_bytes

client = TestClient(app)
WARSAW_TZ = ZoneInfo("Europe/Warsaw")


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
    is_active: bool = True,
    must_change_password: bool = False,
) -> int:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(
                email=email,
                hashed_password=hash_password("Secret123!"),
                role=role,
                is_active=is_active,
                must_change_password=must_change_password,
            )
            db.add(u)
        else:
            u.role = role
            u.is_active = is_active
            u.must_change_password = must_change_password
        db.commit()
        db.refresh(u)
        return u.id


class TestRoleMatrixAuthGuards:
    def test_unauthenticated_requests_rejected_across_all_protected_endpoints(self):
        endpoints = [
            ("GET", "/api/me"),
            ("GET", "/api/cases"),
            ("GET", "/api/dashboard/summary"),
            ("GET", "/api/notifications"),
            ("GET", "/api/import/copies"),
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/settings"),
            ("GET", "/api/admin/audit-log"),
            ("GET", "/api/admin/backups"),
        ]
        for method, path in endpoints:
            res = client.request(method, path)
            assert res.status_code in (401, 403), f"{method} {path} -> {res.status_code}"

    def test_deactivated_user_token_rejected_immediately_with_401(self):
        _ensure_user("edge_deact@example.com", role="user", is_active=True)
        token = _login("edge_deact@example.com")
        # Deactivate directly in DB (JWT still valid cryptographically)
        _ensure_user("edge_deact@example.com", role="user", is_active=False)

        for path in ("/api/me", "/api/cases", "/api/dashboard/summary", "/api/notifications"):
            res = client.get(path, headers=_headers(token))
            assert res.status_code == 401, f"{path} -> {res.status_code}"

    def test_must_change_password_blocks_business_endpoints_with_403_but_allows_me(self):
        _ensure_user(
            "edge_mcp@example.com",
            role="user",
            is_active=True,
            must_change_password=True,
        )
        token = _login("edge_mcp@example.com")

        assert client.get("/api/me", headers=_headers(token)).status_code == 200
        for path in ("/api/cases", "/api/dashboard/summary", "/api/notifications"):
            res = client.get(path, headers=_headers(token))
            assert res.status_code == 403, f"{path} -> {res.status_code}"


class TestExcelAdapterEdgeCases:
    def test_polish_date_formats_and_free_text_warnings(self):
        iso, err, warn = parse_date_value("15.03.2027", allow_free_text_warning=False)
        assert iso == "2027-03-15" and err is None and warn is None

        iso2, err2, warn2 = parse_date_value("2027-04-20", allow_free_text_warning=False)
        assert iso2 == "2027-04-20" and err2 is None and warn2 is None

        # Free-text note in deadline column -> warning (not error) when allowed
        iso3, err3, warn3 = parse_date_value(
            "po dostarczeniu dokumentów", allow_free_text_warning=True
        )
        assert iso3 is None and err3 is None and warn3 is not None

        # Broken numeric date -> error
        iso4, err4, _ = parse_date_value("32.13.2027", allow_free_text_warning=True)
        assert iso4 is None and err4 is not None

    def test_export_and_reimport_roundtrip_preserves_extra_columns(self):
        rows = [
            {
                "row_index": 2,
                "case_number": "RT-001",
                "title": "Sprawa testowa",
                "client_name": "Jan Testowy",
                "assigned_to_email": "trainee@example.com",
                "deadline": "2027-08-01",
                "date_filed": "2027-01-10",
                "status": "open",
                "note": "Notatka startowa",
                "extra_columns": {"APROBANT": "Kowalska", "OFE": "TAK"},
            }
        ]
        xlsx_bytes = build_xlsx_bytes(rows)
        assert len(xlsx_bytes) > 0

        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        assert "APROBANT" in headers
        assert "OFE" in headers

        parsed = parse_excel_bytes(
            filename="roundtrip.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            raw_bytes=xlsx_bytes,
            default_assigned_to_email=None,
        )
        assert len(parsed) == 1
        assert parsed[0]["case_number"] == "RT-001"
        assert parsed[0]["extra_columns"]["APROBANT"] == "Kowalska"
        assert parsed[0]["extra_columns"]["OFE"] == "TAK"


class TestWarsawDateBoundaries:
    def test_today_is_due_soon_not_overdue_and_yesterday_is_overdue(self):
        admin_token = _login("admin@example.com")
        user_token = _login("trainee@example.com")
        with SessionLocal() as db:
            trainee = db.scalar(select(User).where(User.email == "trainee@example.com"))
            assert trainee is not None
            trainee_id = trainee.id

        today = datetime.now(WARSAW_TZ).date()
        tag = datetime.now(timezone.utc).strftime("%H%M%S%f")

        c_yest = client.post(
            "/api/cases",
            json={
                "title": f"Boundary Yest {tag}",
                "client_name": "Klient B",
                "assigned_to": trainee_id,
                "deadline": (today - timedelta(days=1)).isoformat(),
            },
            headers=_headers(admin_token),
        ).json()
        c_today = client.post(
            "/api/cases",
            json={
                "title": f"Boundary Today {tag}",
                "client_name": "Klient B",
                "assigned_to": trainee_id,
                "deadline": today.isoformat(),
            },
            headers=_headers(admin_token),
        ).json()
        c_far = client.post(
            "/api/cases",
            json={
                "title": f"Boundary Far {tag}",
                "client_name": "Klient B",
                "assigned_to": trainee_id,
                "deadline": (today + timedelta(days=90)).isoformat(),
            },
            headers=_headers(admin_token),
        ).json()

        r_ov = client.get(f"/api/cases?q={tag}&overdue=true", headers=_headers(user_token))
        assert [c["id"] for c in r_ov.json()["items"]] == [c_yest["id"]]

        r_ds = client.get(f"/api/cases?q={tag}&due_soon=true", headers=_headers(user_token))
        assert [c["id"] for c in r_ds.json()["items"]] == [c_today["id"]]
        assert c_far["id"] not in [c["id"] for c in r_ds.json()["items"]]
