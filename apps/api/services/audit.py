from datetime import date, datetime, timezone
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import AdminAuditLog, CaseAssignmentHistory, CaseEditLog, CaseNote

logger = logging.getLogger("malinois.audit")

_SENSITIVE_KEY_TOKENS = ("pesel", "password", "haslo")


def _is_sensitive_key(key: str) -> bool:
    low = str(key).lower()
    return any(tok in low for tok in _SENSITIVE_KEY_TOKENS)


def _format_log_value(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def record_assignment_change(
    db: Session,
    *,
    case_id: int,
    new_user_id: int,
    old_user_id: int | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    if old_user_id is not None:
        open_entries = db.scalars(
            select(CaseAssignmentHistory).where(
                CaseAssignmentHistory.case_id == case_id,
                CaseAssignmentHistory.user_id == old_user_id,
                CaseAssignmentHistory.unassigned_at.is_(None),
            )
        ).all()
        for entry in open_entries:
            entry.unassigned_at = now

    db.add(
        CaseAssignmentHistory(
            case_id=case_id,
            user_id=new_user_id,
            assigned_at=now,
            unassigned_at=None,
        )
    )
    db.flush()


def log_admin_action(
    *,
    actor_id: int,
    action: str,
    target_user_id: int | None = None,
    details: dict[str, Any] | None = None,
    db: Session | None = None,
) -> None:
    if db is not None:
        db.add(
            AdminAuditLog(
                actor_id=actor_id,
                action=action,
                target_user_id=target_user_id,
                details=details or {},
                created_at=datetime.now(timezone.utc),
            )
        )
        db.flush()

    logger.info(
        "admin_action=%s actor_id=%s target_user_id=%s details=%s",
        action,
        actor_id,
        target_user_id,
        details or {},
    )


def log_case_changes(
    *,
    case_id: int,
    actor_id: int,
    changes: dict[str, tuple[Any, Any]],
    reason: str | None = None,
    db: Session | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    rows_to_insert: list[CaseEditLog] = []

    for field, (old_val, new_val) in changes.items():
        if field == "extra_fields":
            old_dict = old_val if isinstance(old_val, dict) else {}
            new_dict = new_val if isinstance(new_val, dict) else {}
            all_keys = sorted(set(old_dict.keys()) | set(new_dict.keys()))
            for key in all_keys:
                ov = old_dict.get(key)
                nv = new_dict.get(key)
                if ov == nv:
                    continue
                if _is_sensitive_key(key):
                    ov_str = "[REDACTED]" if ov is not None else None
                    nv_str = "[REDACTED]" if nv is not None else None
                else:
                    ov_str = _format_log_value(ov)
                    nv_str = _format_log_value(nv)
                rows_to_insert.append(
                    CaseEditLog(
                        case_id=case_id,
                        user_id=actor_id,
                        field_name=f"extra:{key}"[:100],
                        old_value=ov_str,
                        new_value=nv_str,
                        reason=None,
                        changed_at=now,
                    )
                )
        else:
            entry_reason = reason if field in ("deadline", "date_filed", "assigned_to") else None
            rows_to_insert.append(
                CaseEditLog(
                    case_id=case_id,
                    user_id=actor_id,
                    field_name=field[:100],
                    old_value=_format_log_value(old_val),
                    new_value=_format_log_value(new_val),
                    reason=entry_reason,
                    changed_at=now,
                )
            )

    if db is not None and rows_to_insert:
        db.add_all(rows_to_insert)
        db.flush()

    logger.info(
        "case_changes case_id=%s actor_id=%s reason=%s count=%s",
        case_id,
        actor_id,
        reason,
        len(rows_to_insert),
    )


def trigger_pre_import_backup(
    *, actor_id: int, copy_id: int, db: Session | None = None
) -> None:
    """Triggers mandatory pre-import backup snapshot (Spec 017)."""
    if db is not None:
        from services import backups as backup_service

        backup_service.create_backup(
            db, backup_type="pre_import", created_by_id=actor_id
        )
    logger.info("pre_import_backup_triggered actor_id=%s copy_id=%s", actor_id, copy_id)


def create_initial_case_note(
    *,
    case_id: int,
    actor_id: int,
    content: str,
    db: Session | None = None,
) -> None:
    text = content.strip()
    if not text:
        return
    if db is not None:
        db.add(
            CaseNote(
                case_id=case_id,
                subject_user_id=None,
                author_id=actor_id,
                content=text[:2000],
                created_at=datetime.now(timezone.utc),
            )
        )
        db.flush()
    logger.info(
        "initial_case_note_created case_id=%s actor_id=%s length=%s",
        case_id,
        actor_id,
        len(text),
    )


def record_last_import_at(
    *,
    actor_id: int,
    timestamp_iso: str,
    db: Session | None = None,
) -> None:
    if db is not None:
        from services.settings import set_system_setting

        set_system_setting(db, "last_import_at", timestamp_iso)
    logger.info("last_import_at_recorded actor_id=%s at=%s", actor_id, timestamp_iso)
