from collections.abc import Callable
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database import get_db
from exceptions import StructuredHTTPException
from models import LoginAuditLog, User
from schemas import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    UISettingsResponse,
    UISettingsUpdateRequest,
    UserResponse,
    UserRole,
)
from security import (
    create_access_token,
    decode_access_token,
    hash_password,
    login_rate_limiter,
    validate_password_policy,
    verify_password,
)
from services import settings as settings_service

router = APIRouter(prefix="/api", tags=["auth"])


def serialize_user(user: User, db: Session) -> UserResponse:
    merged_ui = settings_service.merge_ui_settings(user.ui_settings)
    threshold = settings_service.get_notification_threshold_days(db)
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role,  # type: ignore[arg-type]
        supervisor_id=user.supervisor_id,
        must_change_password=user.must_change_password,
        ui_settings=UISettingsResponse.model_validate(merged_ui),
        notification_threshold_days=threshold,
    )


def get_authenticated_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak nagłówka autoryzacji",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy format tokenu",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = decode_access_token(token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy lub wygasły token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Użytkownik nie istnieje lub jest nieaktywny",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user(
    current_user: User = Depends(get_authenticated_user),
) -> User:
    if current_user.must_change_password:
        raise StructuredHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": "password_change_required",
                "detail": "Musisz zmienić hasło przed kontynuowaniem.",
            },
        )
    return current_user


def require_role(*roles: UserRole) -> Callable[..., User]:
    allowed = set(roles)

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Brak uprawnień do wykonania tej operacji",
            )
        return current_user

    return _checker


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    login_rate_limiter.check(client_ip)

    user = db.scalar(select(User).where(func.lower(User.email) == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        db.add(
            LoginAuditLog(
                attempted_email=payload.email[:255],
                client_ip=client_ip[:64],
                success=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Niepoprawny login lub hasło",
        )

    token = create_access_token(subject=user.email)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=serialize_user(user, db),
    )


@router.get("/me", response_model=UserResponse)
def read_me(
    current_user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    return serialize_user(current_user, db)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Obecne hasło jest nieprawidłowe.",
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nowe hasło musi różnić się od obecnego hasła.",
        )

    try:
        validate_password_policy(payload.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()


@router.patch("/me/settings", response_model=UISettingsResponse)
def update_my_settings(
    payload: UISettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UISettingsResponse:
    merged = settings_service.merge_ui_settings(current_user.ui_settings)
    for field in payload.model_fields_set:
        merged[field] = getattr(payload, field)
    current_user.ui_settings = merged
    db.commit()
    db.refresh(current_user)
    return UISettingsResponse.model_validate(merged)
