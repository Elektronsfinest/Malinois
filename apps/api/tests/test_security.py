import pytest
from security import (
    DEFAULT_DEV_SECRET_KEY,
    hash_password,
    validate_jwt_secret,
    validate_password_policy,
    verify_password,
)


class TestPasswordPolicy:
    def test_accepts_valid_12_char_strong_password(self):
        validate_password_policy("StrongPass1!")
        validate_password_policy("AdminPass123!@#")

    def test_rejects_too_short_password(self):
        with pytest.raises(ValueError, match="12"):
            validate_password_policy("Short1!aaaa")

    def test_rejects_password_over_72_utf8_bytes(self):
        long_ascii = "Aa1!" + "x" * 69  # 73 bytes
        with pytest.raises(ValueError, match="72"):
            validate_password_policy(long_ascii)

        # Multi-byte UTF-8 characters pushing over 72 bytes while < 72 chars
        long_utf8 = "Aa1!" + "ą" * 35  # 4 + 70 = 74 bytes
        with pytest.raises(ValueError, match="72"):
            validate_password_policy(long_utf8)

    def test_rejects_missing_uppercase(self):
        with pytest.raises(ValueError):
            validate_password_policy("lowercase123!")

    def test_rejects_missing_lowercase(self):
        with pytest.raises(ValueError):
            validate_password_policy("UPPERCASE123!")

    def test_rejects_missing_digit(self):
        with pytest.raises(ValueError):
            validate_password_policy("NoDigitsHere!")

    def test_rejects_missing_special_char_or_whitespace_only(self):
        with pytest.raises(ValueError):
            validate_password_policy("NoSpecial1234")
        with pytest.raises(ValueError):
            validate_password_policy("Space Only 123")


class TestBcryptCostAndJwtSecret:
    def test_bcrypt_uses_cost_factor_at_least_12(self):
        hashed = hash_password("StrongPass1!")
        parts = hashed.split("$")
        assert len(parts) >= 4
        rounds = int(parts[2])
        assert rounds >= 12
        assert verify_password("StrongPass1!", hashed) is True

    def test_validate_jwt_secret_rejects_default_in_production(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
        with pytest.raises(RuntimeError):
            validate_jwt_secret()

    def test_validate_jwt_secret_allows_custom_in_production(self, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-prod-key-999")
        validate_jwt_secret()

    def test_validate_jwt_secret_allows_default_in_development(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("JWT_SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
        validate_jwt_secret()
