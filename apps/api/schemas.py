from datetime import date, datetime
from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["admin", "supervisor", "user"]
CaseStatus = Literal["open", "closed"]
UITheme = Literal["dark", "light"]
UIFontSize = Literal["small", "normal", "large", "xl"]


class UISettingsResponse(BaseModel):
    theme: UITheme = "dark"
    font_size: UIFontSize = "normal"
    high_contrast: bool | None = None
    reduced_motion: bool | None = None


class UISettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: UITheme | None = None
    font_size: UIFontSize | None = None
    high_contrast: bool | None = None
    reduced_motion: bool | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetResponse(BaseModel):
    temporary_password: str


class AdminSettingsResponse(BaseModel):
    notification_threshold_days: int


class AdminSettingsUpdateRequest(BaseModel):
    notification_threshold_days: int


class LoginRequest(BaseModel):
    email: str = Field(validation_alias=AliasChoices("email", "username"))
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    role: UserRole
    supervisor_id: int | None
    must_change_password: bool
    ui_settings: UISettingsResponse = Field(default_factory=UISettingsResponse)
    notification_threshold_days: int = 7


class AssignableUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class AdminUserCreateRequest(BaseModel):
    email: str
    password: str
    role: UserRole = "user"
    supervisor_id: int | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class AdminUserUpdateRequest(BaseModel):
    role: UserRole | None = None
    supervisor_id: int | None = None
    is_active: bool | None = None
    reassign_cases_to: int | None = None
    reassign_subordinates_to: int | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_number: str | None
    title: str
    client_name: str
    assigned_to: int
    assigned_to_email: str
    assigned_to_is_active: bool
    deadline: date | None
    date_filed: date | None
    status: CaseStatus
    archived: bool
    is_readonly_archive: bool = False
    version: int
    extra_fields: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    page: int
    page_size: int


class CaseCreateRequest(BaseModel):
    case_number: str | None = None
    title: str
    client_name: str
    assigned_to: int
    deadline: date | None = None
    date_filed: date | None = None
    status: CaseStatus = "open"
    extra_fields: dict[str, Any] | None = None

    @field_validator("case_number")
    @classmethod
    def clean_case_number(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None

    @field_validator("title", "client_name")
    @classmethod
    def strip_required_text(cls, v: str) -> str:
        return v.strip()


class CaseUpdateRequest(BaseModel):
    version: int
    case_number: str | None = None
    title: str | None = None
    client_name: str | None = None
    assigned_to: int | None = None
    deadline: date | None = None
    date_filed: date | None = None
    status: CaseStatus | None = None
    extra_fields: dict[str, Any] | None = None
    reason: str | None = None

    @field_validator("case_number")
    @classmethod
    def clean_case_number(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None

    @field_validator("title", "client_name", "reason")
    @classmethod
    def strip_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()


WorkingCopySourceType = Literal["upload", "snapshot"]
ConflictResolution = Literal["skip", "update_existing"]


class WorkingCopyRow(BaseModel):
    row_index: int
    case_id: int | None = None
    version: int | None = None
    case_number: str | None = None
    title: str | None = None
    client_name: str | None = None
    assigned_to_email: str | None = None
    deadline: str | None = None
    date_filed: str | None = None
    status: CaseStatus = "open"
    note: str | None = None
    extra_columns: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    conflict: bool = False
    resolution: ConflictResolution | None = None


class WorkingCopySummaryResponse(BaseModel):
    id: int
    source_type: WorkingCopySourceType
    label: str
    row_count: int
    error_count: int
    conflict_count: int
    created_at: datetime
    expires_at: datetime


class WorkingCopyDetailResponse(WorkingCopySummaryResponse):
    rows: list[WorkingCopyRow]


class WorkingCopyRowPatch(BaseModel):
    row_index: int
    case_number: str | None = None
    title: str | None = None
    client_name: str | None = None
    assigned_to_email: str | None = None
    deadline: str | None = None
    date_filed: str | None = None
    status: CaseStatus | None = None
    note: str | None = None
    extra_columns: dict[str, Any] | None = None
    resolution: ConflictResolution | None = None


class WorkingCopyPatchRequest(BaseModel):
    rows: list[WorkingCopyRowPatch]


class WorkingCopyCommitConflict(BaseModel):
    row: int
    case_id: int | None = None
    reason: str


class WorkingCopyCommitError(BaseModel):
    row: int
    reason: str


class WorkingCopyCommitResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    conflicts: list[WorkingCopyCommitConflict]
    errors: list[WorkingCopyCommitError]


NotificationUrgency = Literal["upcoming", "overdue"]


class NotificationItemResponse(BaseModel):
    case_id: int
    case_title: str
    client_name: str
    assigned_to_email: str
    deadline: date
    days_remaining: int
    urgency: NotificationUrgency
    version: int


class CaseVersionRequest(BaseModel):
    version: int


class CaseEditLogResponse(BaseModel):
    id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    reason: str | None
    changed_by_email: str
    changed_at: datetime


class AdminAuditLogResponse(BaseModel):
    id: int
    actor_email: str
    action: str
    target_user_id: int | None
    details: dict[str, Any] | None
    created_at: datetime


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogResponse]
    total: int
    page: int
    page_size: int


class CaseNoteCreateRequest(BaseModel):
    content: str
    subject_user_id: int | None = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        return v.strip()


class PersonNoteCreateRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        return v.strip()


class CaseNoteResponse(BaseModel):
    id: int
    case_id: int | None
    subject_user_id: int | None
    subject_email: str | None
    content: str
    author_id: int
    author_email: str
    created_at: datetime


class BulkCaseItem(BaseModel):
    id: int
    version: int


class BulkCaseRequest(BaseModel):
    items: list[BulkCaseItem]
    action: str
    params: dict[str, Any] | None = None


class BulkCaseResponse(BaseModel):
    success: bool = True
    affected_count: int
    action: str


class CaseReassignRequest(BaseModel):
    items: list[BulkCaseItem]
    new_assigned_to: int
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None


class CaseReassignResponse(BaseModel):
    success: bool = True
    reassigned_count: int
    new_assigned_to: int
    new_assigned_to_email: str


class TeamMemberSummaryResponse(BaseModel):
    user_id: int
    email: str
    is_active: bool = True
    open_cases: int
    overdue_cases: int
    due_soon: int


class DashboardSummaryResponse(BaseModel):
    notification_threshold_days: int
    open_cases: int
    overdue_cases: int
    due_soon: int
    closed_this_month: int
    team_summary: list[TeamMemberSummaryResponse] | None = None
    total_cases: int | None = None
    import_last_at: str | None = None


BackupType = Literal["automated", "manual", "pre_import"]


class BackupLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    size_bytes: int
    backup_type: BackupType
    created_at: datetime


class BackupDownloadRequest(BaseModel):
    password: str
