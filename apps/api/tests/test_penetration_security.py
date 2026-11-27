"""
Defensive Security & OWASP Penetration Regression Suite (Spec 007).

Verifies that Malinois security controls hold against hostile inputs:
- A01: Broken Access Control, IDOR, Privilege Escalation, Mass Assignment
- A02: Cryptographic Failures & JWT Tampering (alg=none, wrong secret, expired)
- A03: SQL Injection, Path Traversal, Malicious File Upload / Oversized Payload
- A04/A05: Brute-Force Rate Limiting, Security Headers, Audit & PII Redaction
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import select
from database import SessionLocal
from main import app
from models import Case, CaseEditLog, LoginAuditLog, User
from security import (
    ALGORITHM,
    SECRET_KEY,
    login_rate_limiter,
    validate_jwt_secret,
    validate_password_policy,
)

client = TestClient(app)


def _login(email: str, password: str = "Secret123!") -> str:
    res = client.post("/api/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestA01BrokenAccessControlAndIDOR:
    def test_regular_user_cannot_escalate_privileges_or_access_admin_endpoints(self):
        user_token = _login("trainee@example.com")

        # Admin routes strictly 403
        for method, path in (
            ("GET", "/api/admin/users"),
            ("POST", "/api/admin/users"),
            ("GET", "/api/admin/settings"),
            ("PATCH", "/api/admin/settings"),
            ("GET", "/api/admin/audit-log"),
            ("GET", "/api/admin/backups"),
            ("POST", "/api/admin/backups"),
        ):
            res = client.request(method, path, headers=_headers(user_token), json={})
            assert res.status_code == 403, f"{method} {path} returned {res.status_code}"

        # Mass assignment on /api/me/settings rejected (extra="forbid" -> 422)
        res_ma = client.patch(
            "/api/me/settings",
            json={"theme": "dark", "role": "admin", "is_active": True},
            headers=_headers(user_token),
        )
        assert res_ma.status_code == 422

    def test_idor_cross_user_case_access_returns_404_anti_enumeration(self):
        admin_token = _login("admin@example.com")
        user_token = _login("trainee@example.com")

        with SessionLocal() as db:
            sup = db.scalar(select(User).where(User.email == "sup@example.com"))
            assert sup is not None
            sup_id = sup.id

        sup_case = client.post(
            "/api/cases",
            json={
                "title": "Poufna sprawa przelozonego",
                "client_name": "Tajny Klient",
                "assigned_to": sup_id,
            },
            headers=_headers(admin_token),
        ).json()

        cid = sup_case["id"]
        # Direct GET, PATCH, archive, history, notes must all return 404 (not 403)
        assert client.get(f"/api/cases/{cid}", headers=_headers(user_token)).status_code == 404
        assert (
            client.patch(
                f"/api/cases/{cid}",
                json={"version": sup_case["version"], "title": "Hacked"},
                headers=_headers(user_token),
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/cases/{cid}/archive",
                json={"version": sup_case["version"]},
                headers=_headers(user_token),
            ).status_code
            == 404
        )
        assert (
            client.get(f"/api/cases/{cid}/history", headers=_headers(user_token)).status_code
            == 404
        )
        assert (
            client.get(f"/api/cases/{cid}/notes", headers=_headers(user_token)).status_code
            == 404
        )

    def test_idor_cross_user_working_copy_access_returns_404(self):
        admin_token = _login("admin@example.com")
        user_token = _login("trainee@example.com")

        snap = client.post("/api/import/copies/from-cases", headers=_headers(admin_token))
        assert snap.status_code == 201
        copy_id = snap.json()["id"]

        try:
            assert (
                client.get(f"/api/import/copies/{copy_id}", headers=_headers(user_token)).status_code
                == 404
            )
            assert (
                client.delete(
                    f"/api/import/copies/{copy_id}", headers=_headers(user_token)
                ).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/import/copies/{copy_id}/commit", headers=_headers(user_token)
                ).status_code
                == 404
            )
        finally:
            client.delete(f"/api/import/copies/{copy_id}", headers=_headers(admin_token))


class TestA02CryptographicAndJWTSecurity:
    def test_jwt_tampering_alg_none_wrong_secret_and_expired_rejected(self):
        now = datetime.now(timezone.utc)

        # 1. alg=none unsigned token
        none_token = jwt.encode(
            {"sub": "admin@example.com", "exp": now + timedelta(minutes=30)},
            key="",
            algorithm="none",
        )
        assert client.get("/api/me", headers=_headers(none_token)).status_code == 401

        # 2. Signed with wrong secret
        wrong_secret_token = jwt.encode(
            {"sub": "admin@example.com", "exp": now + timedelta(minutes=30)},
            key="attacker-forged-secret-key",
            algorithm=ALGORITHM,
        )
        assert client.get("/api/me", headers=_headers(wrong_secret_token)).status_code == 401

        # 3. Expired token
        expired_token = jwt.encode(
            {"sub": "admin@example.com", "exp": now - timedelta(seconds=10)},
            key=SECRET_KEY,
            algorithm=ALGORITHM,
        )
        assert client.get("/api/me", headers=_headers(expired_token)).status_code == 401

        # 4. Missing sub claim
        no_sub_token = jwt.encode(
            {"role": "admin", "exp": now + timedelta(minutes=30)},
            key=SECRET_KEY,
            algorithm=ALGORITHM,
        )
        assert client.get("/api/me", headers=_headers(no_sub_token)).status_code == 401

    def test_production_rejects_default_jwt_secret(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setattr("security.SECRET_KEY", "dev-secret-key-change-in-production")
        with pytest.raises(RuntimeError):
            validate_jwt_secret()

    def test_password_policy_rejects_weak_and_overlong_passwords(self):
        weak_samples = [
            "Short1!",  # < 12 chars
            "alllowercase1!",  # no uppercase
            "ALLUPPERCASE1!",  # no lowercase
            "NoDigitsHere!!",  # no digit
            "NoSpecialChar12",  # no special char
            "A" * 70 + "a1!",  # > 72 UTF-8 bytes
        ]
        for pwd in weak_samples:
            with pytest.raises(ValueError):
                validate_password_policy(pwd)

        validate_password_policy("StrongPass123!")


class TestA03InjectionAndUploadSecurity:
    def test_sql_injection_payloads_safely_parameterized(self):
        admin_token = _login("admin@example.com")
        sqli_payloads = [
            "' OR '1'='1",
            "admin@example.com' --",
            "'; DROP TABLE cases; --",
            "' UNION SELECT id, email, hashed_password FROM users --",
        ]

        # Login endpoint never authenticates on SQLi
        for payload in sqli_payloads:
            login_rate_limiter.reset()
            res = client.post("/api/login", json={"email": payload, "password": "x"})
            assert res.status_code == 401

        # Search endpoint never errors or leaks unauthorized rows
        for payload in sqli_payloads:
            res = client.get("/api/cases", params={"q": payload}, headers=_headers(admin_token))
            assert res.status_code == 200
            assert "items" in res.json()

        # Verify cases table still intact
        with SessionLocal() as db:
            assert db.scalar(select(Case.id).limit(1)) is not None

    def test_backup_download_blocks_path_traversal_and_invalid_filenames(self):
        admin_token = _login("admin@example.com")
        malicious_names = [
            "../dev.db",
            "..%2Fdev.db",
            "..\\dev.db",
            "malinois_backup_20260101_000000_manual.sqlite.gz/../../dev.db",
            "dev.db",
            "malinois_backup_20260101_000000_manual.sql.gz;rm -rf /",
        ]
        for name in malicious_names:
            res = client.post(
                f"/api/admin/backups/{name}/download",
                json={"password": "Secret123!"},
                headers=_headers(admin_token),
            )
            if name in ("dev.db", "malinois_backup_20260101_000000_manual.sql.gz;rm -rf /"):
                assert res.status_code == 400, f"{name} -> {res.status_code}"
            else:
                assert res.status_code in (400, 404), f"{name} -> {res.status_code}"

    def test_malicious_and_oversized_file_uploads_rejected(self):
        admin_token = _login("admin@example.com")

        # Disguised HTML / executable with fake extension or bad MIME
        bad_uploads = [
            ("exploit.html", b"<script>alert(1)</script>", "text/html"),
            ("malware.exe", b"MZ\x90\x00", "application/octet-stream"),
            (
                "fake.xlsx",
                b"not a real zip or excel file",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        ]
        for fname, content, mime in bad_uploads:
            res = client.post(
                "/api/import/copies/upload",
                files={"file": (fname, BytesIO(content), mime)},
                headers=_headers(admin_token),
            )
            assert res.status_code == 400, f"{fname} -> {res.status_code}"

        # Oversized > 10 MB payload -> 413
        oversized = b"0" * (10 * 1024 * 1024 + 1024)
        res_big = client.post(
            "/api/import/copies/upload",
            files={
                "file": (
                    "huge.xlsx",
                    BytesIO(oversized),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=_headers(admin_token),
        )
        assert res_big.status_code == 413


class TestA04A05HeadersRateLimitAndPIIRedaction:
    def test_security_headers_present_on_api_responses(self):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("x-frame-options") == "DENY"
        assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in (res.headers.get("content-security-policy") or "")

    def test_login_brute_force_rate_limited_and_passwords_never_logged(self):
        login_rate_limiter.reset()
        secret_attempt = "SuperSecretWrongPass99!"
        for _ in range(10):
            r = client.post(
                "/api/login",
                json={"email": "bruteforce@example.com", "password": secret_attempt},
            )
            assert r.status_code == 401

        # 11th request within 60s must be blocked with 429
        r_blocked = client.post(
            "/api/login",
            json={"email": "bruteforce@example.com", "password": secret_attempt},
        )
        assert r_blocked.status_code == 429

        # Audit table stores attempted email & IP, never the password
        with SessionLocal() as db:
            log = db.scalar(
                select(LoginAuditLog)
                .where(LoginAuditLog.attempted_email == "bruteforce@example.com")
                .order_by(LoginAuditLog.id.desc())
            )
            assert log is not None
            assert secret_attempt not in log.attempted_email
            assert secret_attempt not in log.client_ip

    def test_pesel_redacted_in_case_edit_log(self):
        admin_token = _login("admin@example.com")
        with SessionLocal() as db:
            trainee = db.scalar(select(User).where(User.email == "trainee@example.com"))
            assert trainee is not None
            trainee_id = trainee.id

        c = client.post(
            "/api/cases",
            json={
                "title": "Sprawa PII",
                "client_name": "Jan PII",
                "assigned_to": trainee_id,
                "extra_fields": {"Pesel": "90010112345"},
            },
            headers=_headers(admin_token),
        ).json()

        r_patch = client.patch(
            f"/api/cases/{c['id']}",
            json={
                "version": c["version"],
                "extra_fields": {"Pesel": "92020254321"},
            },
            headers=_headers(admin_token),
        )
        assert r_patch.status_code == 200

        with SessionLocal() as db:
            edit = db.scalar(
                select(CaseEditLog)
                .where(CaseEditLog.case_id == c["id"], CaseEditLog.field_name == "extra:Pesel")
            )
            assert edit is not None
            assert edit.old_value == "[REDACTED]"
            assert edit.new_value == "[REDACTED]"
            assert "90010112345" not in (edit.old_value or "")
            assert "92020254321" not in (edit.new_value or "")
