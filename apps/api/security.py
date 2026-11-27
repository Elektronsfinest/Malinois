from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import os
import secrets
import string
import time
import bcrypt
from fastapi import HTTPException, status
import jwt

DEFAULT_DEV_SECRET_KEY = "dev-secret-key-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_DEV_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
BCRYPT_ROUNDS = 12
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 72
LOGIN_RATE_LIMIT_MAX = 10
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60.0

_SPECIAL_CHARS = "!@#$%^&*()-_=+"


class LoginRateLimiter:
    def __init__(
        self,
        max_requests: int = LOGIN_RATE_LIMIT_MAX,
        window_seconds: float = LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        q = self._hits[client_ip]
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Zbyt wiele prób logowania. Spróbuj ponownie za minutę.",
            )
        q.append(now)

    def reset(self) -> None:
        self._hits.clear()


login_rate_limiter = LoginRateLimiter()


def validate_jwt_secret() -> None:
    env = os.getenv("ENV", "development").lower()
    secret = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    if env == "production" and (not secret or secret == DEFAULT_DEV_SECRET_KEY):
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a secure non-default value when ENV=production"
        )


def validate_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Hasło musi mieć co najmniej 12 znaków.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Hasło nie może przekraczać 72 bajtów.")
    if not any(c.isupper() for c in password):
        raise ValueError("Hasło musi zawierać co najmniej jedną wielką literę.")
    if not any(c.islower() for c in password):
        raise ValueError("Hasło musi zawierać co najmniej jedną małą literę.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Hasło musi zawierać co najmniej jedną cyfrę.")
    if not any(not c.isalnum() and not c.isspace() for c in password):
        raise ValueError("Hasło musi zawierać co najmniej jeden znak specjalny.")


def generate_temporary_password(length: int = 16) -> str:
    target_len = max(length, MIN_PASSWORD_LENGTH)
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SPECIAL_CHARS),
    ]
    alphabet = string.ascii_letters + string.digits + _SPECIAL_CHARS
    chars.extend(secrets.choice(alphabet) for _ in range(target_len - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    )
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        encoded_password = plain_password.encode("utf-8")
        if len(encoded_password) > MAX_PASSWORD_BYTES:
            return False
        return bcrypt.checkpw(encoded_password, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            return None
        return subject
    except jwt.PyJWTError:
        return None
