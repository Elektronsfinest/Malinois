from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import require_role, serialize_user
from schemas import (
    AdminSettingsResponse,
    AdminSettingsUpdateRequest,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    PasswordResetResponse,
    UserResponse,
    UserRole,
)
from services import settings as settings_service
from services import users as user_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def list_admin_users(
    role: UserRole | None = None,
    supervisor_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> list[UserResponse]:
    users = user_service.list_users(
        db, role=role, supervisor_id=supervisor_id, is_active=is_active
    )
    return [serialize_user(u, db) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
) -> UserResponse:
    user = user_service.create_user(db, payload, actor=actor)
    return serialize_user(user, db)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
) -> UserResponse:
    user = user_service.update_user(db, user_id, payload, actor=actor)
    return serialize_user(user, db)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_admin_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
) -> PasswordResetResponse:
    temp_password = user_service.reset_user_password(db, user_id, actor=actor)
    return PasswordResetResponse(temporary_password=temp_password)


@router.get("/settings", response_model=AdminSettingsResponse)
def get_admin_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> AdminSettingsResponse:
    days = settings_service.get_notification_threshold_days(db)
    return AdminSettingsResponse(notification_threshold_days=days)


@router.patch("/settings", response_model=AdminSettingsResponse)
def patch_admin_settings(
    payload: AdminSettingsUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
) -> AdminSettingsResponse:
    updated = settings_service.update_admin_settings(
        db,
        actor=actor,
        notification_threshold_days=payload.notification_threshold_days,
    )
    return AdminSettingsResponse(**updated)
