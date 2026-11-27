from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import SystemSetting, User
from services.audit import log_admin_action

DEFAULT_NOTIFICATION_THRESHOLD_DAYS = 7
DEFAULT_UI_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "font_size": "normal",
    "high_contrast": None,
    "reduced_motion": None,
}


def merge_ui_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_UI_SETTINGS)
    if isinstance(raw, dict):
        for key in DEFAULT_UI_SETTINGS:
            if key in raw:
                merged[key] = raw[key]
    return merged


def get_system_setting(db: Session, key: str) -> str | None:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return row.value if row is not None else None


def set_system_setting(db: Session, key: str, value: str) -> None:
    now = datetime.now(timezone.utc)
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if row is None:
        db.add(SystemSetting(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now
    db.flush()


def get_notification_threshold_days(db: Session) -> int:
    raw = get_system_setting(db, "notification_threshold_days")
    if raw is None:
        return DEFAULT_NOTIFICATION_THRESHOLD_DAYS
    try:
        val = int(raw)
        if 1 <= val <= 365:
            return val
    except ValueError:
        pass
    return DEFAULT_NOTIFICATION_THRESHOLD_DAYS


def update_admin_settings(
    db: Session,
    *,
    actor: User,
    notification_threshold_days: int,
) -> dict[str, int]:
    if notification_threshold_days < 1 or notification_threshold_days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Próg powiadomień musi być liczbą całkowitą z zakresu 1–365.",
        )

    old_val = get_notification_threshold_days(db)
    set_system_setting(db, "notification_threshold_days", str(notification_threshold_days))
    log_admin_action(
        db=db,
        actor_id=actor.id,
        action="settings_updated",
        target_user_id=None,
        details={
            "key": "notification_threshold_days",
            "old_value": old_val,
            "new_value": notification_threshold_days,
        },
    )
    db.commit()
    return {"notification_threshold_days": notification_threshold_days}
