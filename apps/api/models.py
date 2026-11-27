from datetime import date, datetime, timezone
from typing import Any
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), default="user", server_default="user", nullable=False
    )
    supervisor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_users_supervisor_id_users"),
        index=True,
        nullable=True,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    ui_settings: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_number: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    assigned_to: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_cases_assigned_to_users"),
        index=True,
        nullable=False,
    )
    deadline: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    date_filed: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="open", server_default="open", nullable=False
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    extra_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    assignee: Mapped[User] = relationship("User", foreign_keys=[assigned_to])


class WorkingCopy(Base):
    __tablename__ = "working_copies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_working_copies_owner_id_users"),
        index=True,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    rows_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )


class NotificationDismissal(Base):
    __tablename__ = "notification_dismissals"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_notif_dismissals_user_id"),
        primary_key=True,
        nullable=False,
    )
    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cases.id", name="fk_notif_dismissals_case_id"),
        primary_key=True,
        nullable=False,
    )
    deadline_snapshot: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    state: Mapped[str] = mapped_column(
        String(20), primary_key=True, nullable=False
    )
    dismissed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class CaseAssignmentHistory(Base):
    __tablename__ = "case_assignment_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cases.id", name="fk_case_assign_hist_case_id"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_case_assign_hist_user_id"),
        index=True,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CaseEditLog(Base):
    __tablename__ = "case_edit_log"
    __table_args__ = (
        Index("ix_case_edit_log_case_id_changed_at", "case_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cases.id", name="fk_case_edit_log_case_id"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_case_edit_log_user_id"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_admin_audit_log_actor_id"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_admin_audit_log_target_user_id"),
        nullable=True,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )

    actor: Mapped[User] = relationship("User", foreign_keys=[actor_id])


class CaseNote(Base):
    __tablename__ = "case_notes"
    __table_args__ = (
        CheckConstraint(
            "case_id IS NOT NULL OR subject_user_id IS NOT NULL",
            name="ck_case_notes_case_or_subject",
        ),
        Index("ix_case_notes_case_id_created_at", "case_id", "created_at"),
        Index("ix_case_notes_subject_user_id_created_at", "subject_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cases.id", name="fk_case_notes_case_id"),
        index=True,
        nullable=True,
    )
    subject_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_case_notes_subject_user_id"),
        index=True,
        nullable=True,
    )
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_case_notes_author_id"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    author: Mapped[User] = relationship("User", foreign_keys=[author_id])
    subject_user: Mapped[User | None] = relationship("User", foreign_keys=[subject_user_id])


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class LoginAuditLog(Base):
    __tablename__ = "login_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempted_email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )


class BackupLog(Base):
    __tablename__ = "backup_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    backup_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_backup_logs_created_by_id"),
        nullable=True,
    )
