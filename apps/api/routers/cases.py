from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import get_current_user, require_role
from schemas import (
    AssignableUserResponse,
    BulkCaseRequest,
    BulkCaseResponse,
    CaseCreateRequest,
    CaseListResponse,
    CaseReassignRequest,
    CaseReassignResponse,
    CaseResponse,
    CaseUpdateRequest,
    CaseVersionRequest,
)
from services import cases as case_service

router = APIRouter(prefix="/api", tags=["cases"])


@router.get("/cases", response_model=CaseListResponse)
def list_cases(
    page: int = 1,
    page_size: int = 50,
    archived: bool = False,
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_to: int | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    overdue: bool | None = None,
    due_soon: bool | None = None,
    sort: str = "deadline_asc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseListResponse:
    items, total = case_service.list_cases(
        db,
        current_user,
        page=page,
        page_size=page_size,
        archived=archived,
        q=q,
        status_filter=status_filter,
        assigned_to=assigned_to,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        overdue=overdue,
        due_soon=due_soon,
        sort=sort,
    )
    return CaseListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/cases/bulk", response_model=BulkCaseResponse)
def bulk_cases(
    payload: BulkCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkCaseResponse:
    return case_service.bulk_cases(db, current_user, payload)


@router.post("/cases/reassign", response_model=CaseReassignResponse)
def reassign_cases(
    payload: CaseReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseReassignResponse:
    return case_service.reassign_cases(db, current_user, payload)


@router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseResponse:
    return case_service.create_case(db, current_user, payload)


@router.get("/cases/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseResponse:
    case, is_readonly = case_service.get_case_readable(db, current_user, case_id)
    return case_service.serialize_case(case, is_readonly_archive=is_readonly)


@router.patch("/cases/{case_id}", response_model=CaseResponse)
def patch_case(
    case_id: int,
    payload: CaseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseResponse:
    return case_service.update_case(db, current_user, case_id, payload)


@router.post("/cases/{case_id}/archive", response_model=CaseResponse)
def archive_case(
    case_id: int,
    payload: CaseVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseResponse:
    return case_service.archive_case(db, current_user, case_id, payload.version)


@router.post("/cases/{case_id}/restore", response_model=CaseResponse)
def restore_case(
    case_id: int,
    payload: CaseVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseResponse:
    return case_service.restore_case(db, current_user, case_id, payload.version)


@router.get("/users/assignable", response_model=list[AssignableUserResponse])
def list_assignable_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "supervisor")),
) -> list[AssignableUserResponse]:
    users = case_service.list_assignable_users(db, current_user)
    return [AssignableUserResponse.model_validate(u) for u in users]
