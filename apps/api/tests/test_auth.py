from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

TEST_USER_EMAIL = "trainee@example.com"
TEST_USER_PASSWORD = "Secret123!"


def _extract_token(data: dict) -> str | None:
    """Pomocnicza funkcja pobierająca token niezależnie od nazwy klucza (token / access_token)."""
    return data.get("access_token") or data.get("token")


class TestLoginEndpoint:
    def test_login_success_returns_200_token_and_user_data(self):
        response = client.post(
            "/api/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        )
        assert response.status_code == 200, (
            f"Oczekiwano 200 OK dla poprawnego logowania, otrzymano {response.status_code}"
        )
        data = response.json()

        token = _extract_token(data)
        assert token is not None and isinstance(token, str) and len(token) > 0, (
            "Odpowiedź /api/login musi zawierać niepusty token ('token' lub 'access_token')"
        )

        user_info = data.get("user", data)
        user_identifier = user_info.get("email") or user_info.get("username")
        assert user_identifier == TEST_USER_EMAIL, (
            "Odpowiedź /api/login musi zawierać podstawowe dane użytkownika (email/username)"
        )

    def test_login_wrong_password_returns_401_with_message(self):
        response = client.post(
            "/api/login",
            json={"email": TEST_USER_EMAIL, "password": "WrongPassword!"},
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data or "message" in data

    def test_login_nonexistent_user_returns_401(self):
        response = client.post(
            "/api/login",
            json={"email": "unknown@example.com", "password": TEST_USER_PASSWORD},
        )
        assert response.status_code == 401


class TestMeEndpoint:
    def test_me_authenticated_returns_user_info(self):
        login_res = client.post(
            "/api/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        )
        assert login_res.status_code == 200
        token = _extract_token(login_res.json())
        assert token is not None

        response = client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        user_identifier = data.get("email") or data.get("username")
        assert user_identifier == TEST_USER_EMAIL

    def test_me_without_authorization_header_returns_401_or_403(self):
        response = client.get("/api/me")
        assert response.status_code in (401, 403)

    def test_me_with_invalid_token_returns_401(self):
        response = client.get(
            "/api/me",
            headers={"Authorization": "Bearer invalid-token-value"},
        )
        assert response.status_code == 401


class TestCORSConfiguration:
    def test_cors_headers_present_for_frontend_origin(self):
        frontend_origin = "http://localhost:5173"
        response = client.options(
            "/api/login",
            headers={
                "Origin": frontend_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        assert response.status_code in (200, 204)
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin in (frontend_origin, "*"), (
            "Backend musi mieć skonfigurowany CORSMiddleware dla frontendu"
        )
