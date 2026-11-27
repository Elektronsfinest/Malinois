from datetime import date, datetime, timedelta, timezone
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from exceptions import StructuredHTTPException
from models import Case, User, WorkingCopy
from schemas import (
    CaseCreateRequest,
    CaseUpdateRequest,
    WorkingCopyCommitConflict,
    WorkingCopyCommitError,
    WorkingCopyCommitResponse,
    WorkingCopyDetailResponse,
    WorkingCopyPatchRequest,
    WorkingCopyRow,
    WorkingCopySummaryResponse,
)
from services.audit import (
    create_initial_case_note,
    record_last_import_at,
    trigger_pre_import_backup,
)
from services import cases as case_service
from services.excel_adapter import (
    build_xlsx_bytes,
    parse_date_value,
    parse_excel_bytes,
    sanitize_label,
)

MAX_ACTIVE_COPIES_PER_USER = 5
WORKING_COPY_TTL_HOURS = 24


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _prune_expired_copies(db: Session, owner_id: int) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        delete(WorkingCopy).where(
            WorkingCopy.owner_id == owner_id,
            WorkingCopy.expires_at <= now,
        )
    )
    db.flush()


def _enforce_copy_limit(db: Session, owner_id: int) -> None:
    _prune_expired_copies(db, owner_id)
    active_count = db.scalar(
        select(func.count(WorkingCopy.id)).where(WorkingCopy.owner_id == owner_id)
    )
    if (active_count or 0) >= MAX_ACTIVE_COPIES_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Osiągnięto limit 5 aktywnych kopii roboczych. Usuń starszą kopię, aby utworzyć nową.",
        )


def _validate_and_enrich_rows(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    source_type: str,
) -> list[dict[str, Any]]:
    # Build email -> user map and case_number -> live Case map
    users_by_email = {
        u.email.lower(): u for u in db.scalars(select(User)).all()
    }
    case_numbers = [
        r["case_number"] for r in rows if r.get("case_number")
    ]
    live_by_number: dict[str, Case] = {}
    if case_numbers:
        live_cases = db.scalars(
            select(Case).where(Case.case_number.in_(set(case_numbers)))
        ).all()
        live_by_number = {c.case_number: c for c in live_cases if c.case_number}

    seen_in_file: set[str] = set()
    enriched: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)
        # Preserve parser-originated date errors/warnings, recompute structural/DB checks
        base_errors = [
            e for e in (item.get("errors") or [])
            if "format daty" in e.lower() or "epwd" in e.lower()
        ]
        errors: list[str] = list(base_errors)
        warnings: list[str] = list(item.get("warnings") or [])

        if not (item.get("title") or "").strip():
            errors.append("Brak tytułu sprawy.")
        if not (item.get("client_name") or "").strip():
            errors.append("Brak nazwy klienta.")

        email = (item.get("assigned_to_email") or "").strip().lower()
        if not email:
            errors.append("Brak przypisanego pracownika (email).")
        elif email not in users_by_email:
            errors.append(f"Użytkownik „{email}” nie istnieje w systemie.")

        # Validate ISO date strings if manually edited
        for date_field in ("deadline", "date_filed"):
            val = item.get(date_field)
            if val is not None and str(val).strip() != "":
                iso_d, err, _ = parse_date_value(val, allow_free_text_warning=False)
                if err:
                    if err not in errors:
                        errors.append(err)
                else:
                    item[date_field] = iso_d

        cn = (item.get("case_number") or "").strip() or None
        item["case_number"] = cn

        conflict = False
        if cn:
            if cn in seen_in_file:
                errors.append(f"Duplikat numeru sprawy „{cn}” w tym samym pliku.")
            else:
                seen_in_file.add(cn)

            if source_type == "upload" and cn in live_by_number:
                live = live_by_number[cn]
                conflict = True
                item["case_id"] = live.id
                item["version"] = live.version
            elif source_type == "upload":
                item["case_id"] = None
                item["version"] = None
                item["resolution"] = None

        item["conflict"] = conflict
        item["errors"] = errors
        item["warnings"] = warnings
        enriched.append(item)

    return enriched


def _to_summary(copy: WorkingCopy) -> WorkingCopySummaryResponse:
    rows = copy.rows_json or []
    error_count = sum(1 for r in rows if r.get("errors"))
    conflict_count = sum(
        1 for r in rows if r.get("conflict") and not r.get("resolution")
    )
    return WorkingCopySummaryResponse(
        id=copy.id,
        source_type=copy.source_type,  # type: ignore[arg-type]
        label=copy.label,
        row_count=len(rows),
        error_count=error_count,
        conflict_count=conflict_count,
        created_at=_as_utc(copy.created_at),
        expires_at=_as_utc(copy.expires_at),
    )


def _to_detail(copy: WorkingCopy) -> WorkingCopyDetailResponse:
    summary = _to_summary(copy)
    return WorkingCopyDetailResponse(
        **summary.model_dump(),
        rows=[WorkingCopyRow.model_validate(r) for r in (copy.rows_json or [])],
    )


def get_copy_owned(db: Session, actor: User, copy_id: int) -> WorkingCopy:
    copy = db.scalar(select(WorkingCopy).where(WorkingCopy.id == copy_id))
    now = datetime.now(timezone.utc)
    if (
        copy is None
        or copy.owner_id != actor.id
        or _as_utc(copy.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kopia robocza nie została znaleziona lub wygasła.",
        )
    return copy


def list_copies(db: Session, actor: User) -> list[WorkingCopySummaryResponse]:
    _prune_expired_copies(db, actor.id)
    db.commit()
    copies = list(
        db.scalars(
            select(WorkingCopy)
            .where(WorkingCopy.owner_id == actor.id)
            .order_by(WorkingCopy.created_at.desc())
        ).all()
    )
    return [_to_summary(c) for c in copies]


def create_copy_from_upload(
    db: Session,
    actor: User,
    *,
    filename: str | None,
    content_type: str | None,
    raw_bytes: bytes,
    default_assigned_to: int | None = None,
) -> WorkingCopyDetailResponse:
    if actor.role not in ("admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko administrator lub przełożony może wgrywać pliki Excel.",
        )

    _enforce_copy_limit(db, actor.id)

    default_email: str | None = None
    if default_assigned_to is not None:
        assignee = db.scalar(select(User).where(User.id == default_assigned_to))
        if assignee is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wybrany domyślny pracownik nie istnieje.",
            )
        if actor.role == "supervisor":
            assignable_ids = {u.id for u in case_service.list_assignable_users(db, actor)}
            if assignee.id not in assignable_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Przełożony może przypisywać importowane sprawy wyłącznie sobie lub swoim podwładnym.",
                )
        default_email = assignee.email.lower()

    parsed = parse_excel_bytes(
        filename=filename,
        content_type=content_type,
        raw_bytes=raw_bytes,
        default_assigned_to_email=default_email,
    )
    enriched = _validate_and_enrich_rows(db, parsed, source_type="upload")

    now = datetime.now(timezone.utc)
    copy = WorkingCopy(
        owner_id=actor.id,
        source_type="upload",
        label=sanitize_label(filename),
        rows_json=enriched,
        created_at=now,
        expires_at=now + timedelta(hours=WORKING_COPY_TTL_HOURS),
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _to_detail(copy)


def create_copy_from_cases(db: Session, actor: User) -> WorkingCopyDetailResponse:
    _enforce_copy_limit(db, actor.id)

    items, _ = case_service.list_cases(db, actor, page=1, page_size=200)
    rows: list[dict[str, Any]] = []
    for idx, c in enumerate(items, start=2):
        rows.append(
            {
                "row_index": idx,
                "case_id": c.id,
                "version": c.version,
                "case_number": c.case_number,
                "title": c.title,
                "client_name": c.client_name,
                "assigned_to_email": c.assigned_to_email,
                "deadline": c.deadline.isoformat() if c.deadline else None,
                "date_filed": c.date_filed.isoformat() if c.date_filed else None,
                "status": c.status,
                "note": None,
                "extra_columns": dict(c.extra_fields or {}),
                "errors": [],
                "warnings": [],
                "conflict": False,
                "resolution": None,
            }
        )

    now = datetime.now(timezone.utc)
    copy = WorkingCopy(
        owner_id=actor.id,
        source_type="snapshot",
        label=f"Kopia bieżących spraw ({now.strftime('%d.%m.%Y %H:%M')})",
        rows_json=rows,
        created_at=now,
        expires_at=now + timedelta(hours=WORKING_COPY_TTL_HOURS),
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _to_detail(copy)


def patch_copy(
    db: Session,
    actor: User,
    copy_id: int,
    payload: WorkingCopyPatchRequest,
) -> WorkingCopyDetailResponse:
    copy = get_copy_owned(db, actor, copy_id)
    rows_by_index = {int(r["row_index"]): dict(r) for r in (copy.rows_json or [])}

    for patch in payload.rows:
        if patch.row_index not in rows_by_index:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Wiersz {patch.row_index} nie istnieje w tej kopii roboczej.",
            )
        row = rows_by_index[patch.row_index]
        fields = patch.model_fields_set

        if actor.role != "admin":
            if "deadline" in fields and patch.deadline != row.get("deadline"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tylko administrator może modyfikować kolumnę terminu.",
                )
            if "date_filed" in fields and patch.date_filed != row.get("date_filed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tylko administrator może modyfikować datę wpływu.",
                )

        # Clear stale parser errors on fields being explicitly edited
        if "deadline" in fields or "date_filed" in fields:
            row["errors"] = []

        for key in (
            "case_number",
            "title",
            "client_name",
            "assigned_to_email",
            "deadline",
            "date_filed",
            "status",
            "note",
            "extra_columns",
            "resolution",
        ):
            if key in fields:
                val = getattr(patch, key)
                if key == "assigned_to_email" and isinstance(val, str):
                    val = val.strip().lower() or None
                row[key] = val

        rows_by_index[patch.row_index] = row

    ordered_rows = [rows_by_index[k] for k in sorted(rows_by_index.keys())]
    enriched = _validate_and_enrich_rows(db, ordered_rows, source_type=copy.source_type)
    copy.rows_json = enriched
    db.commit()
    db.refresh(copy)
    return _to_detail(copy)


def delete_copy(db: Session, actor: User, copy_id: int) -> None:
    copy = get_copy_owned(db, actor, copy_id)
    db.delete(copy)
    db.commit()


def download_copy_bytes(db: Session, actor: User, copy_id: int) -> tuple[bytes, str]:
    copy = get_copy_owned(db, actor, copy_id)
    data = build_xlsx_bytes(copy.rows_json or [])
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"malinois-copy-{copy.id}-{today_str}.xlsx"
    return data, filename


def commit_copy(
    db: Session,
    actor: User,
    copy_id: int,
) -> WorkingCopyCommitResponse:
    copy = get_copy_owned(db, actor, copy_id)

    if copy.source_type == "upload" and actor.role not in ("admin", "supervisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tylko administrator lub przełożony może zatwierdzać import z pliku Excel.",
        )

    rows = _validate_and_enrich_rows(db, copy.rows_json or [], source_type=copy.source_type)
    unresolved_errors = [r for r in rows if r.get("errors")]
    unresolved_conflicts = [
        r for r in rows if r.get("conflict") and r.get("resolution") not in ("skip", "update_existing")
    ]
    if unresolved_errors or unresolved_conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie można zatwierdzić kopii: pozostały nierozwiązane błędy walidacji lub konflikty duplikatów.",
        )

    trigger_pre_import_backup(actor_id=actor.id, copy_id=copy.id, db=db)

    users_by_email = {
        u.email.lower(): u for u in db.scalars(select(User)).all()
    }

    created = 0
    updated = 0
    skipped = 0
    conflicts: list[WorkingCopyCommitConflict] = []
    errors: list[WorkingCopyCommitError] = []
    refreshed_rows: list[dict[str, Any]] = []

    for row in rows:
        row_copy = dict(row)
        row_idx = int(row_copy["row_index"])

        if row_copy.get("conflict") and row_copy.get("resolution") == "skip":
            skipped += 1
            refreshed_rows.append(row_copy)
            continue

        email = (row_copy.get("assigned_to_email") or "").strip().lower()
        assignee = users_by_email.get(email)
        if assignee is None:
            errors.append(
                WorkingCopyCommitError(row=row_idx, reason=f"Użytkownik „{email}” nie istnieje.")
            )
            refreshed_rows.append(row_copy)
            continue

        deadline_val = date.fromisoformat(row_copy["deadline"]) if row_copy.get("deadline") else None
        date_filed_val = date.fromisoformat(row_copy["date_filed"]) if row_copy.get("date_filed") else None
        extra_cols = row_copy.get("extra_columns") or None

        try:
            if row_copy.get("case_id") is not None:
                update_kwargs: dict[str, Any] = {
                    "version": int(row_copy.get("version") or 1),
                    "title": row_copy["title"],
                    "client_name": row_copy["client_name"],
                    "status": row_copy.get("status") or "open",
                    "extra_fields": extra_cols,
                }
                if actor.role == "admin":
                    update_kwargs["case_number"] = row_copy.get("case_number")
                    update_kwargs["assigned_to"] = assignee.id
                    update_kwargs["deadline"] = deadline_val
                    update_kwargs["date_filed"] = date_filed_val
                    update_kwargs["reason"] = "Import / aktualizacja z kopii roboczej"

                updated_case = case_service.update_case(
                    db,
                    actor,
                    int(row_copy["case_id"]),
                    CaseUpdateRequest(**update_kwargs),
                )
                updated += 1
                row_copy["case_id"] = updated_case.id
                row_copy["version"] = updated_case.version
                row_copy["conflict"] = False
                row_copy["resolution"] = None
            else:
                created_case = case_service.create_case(
                    db,
                    actor,
                    CaseCreateRequest(
                        case_number=row_copy.get("case_number"),
                        title=row_copy["title"],
                        client_name=row_copy["client_name"],
                        assigned_to=assignee.id,
                        deadline=deadline_val,
                        date_filed=date_filed_val,
                        status=row_copy.get("status") or "open",
                        extra_fields=extra_cols,
                    ),
                    allow_imported_dates=(copy.source_type == "upload"),
                )
                created += 1
                row_copy["case_id"] = created_case.id
                row_copy["version"] = created_case.version
                row_copy["conflict"] = False
                row_copy["resolution"] = None

            note_text = (row_copy.get("note") or "").strip()
            if note_text and row_copy.get("case_id") is not None:
                create_initial_case_note(
                    db=db,
                    case_id=int(row_copy["case_id"]),
                    actor_id=actor.id,
                    content=note_text,
                )
        except StructuredHTTPException as exc:
            if exc.status_code == status.HTTP_409_CONFLICT:
                conflicts.append(
                    WorkingCopyCommitConflict(
                        row=row_idx,
                        case_id=row_copy.get("case_id"),
                        reason=str(exc.content.get("detail") or "Konflikt wersji."),
                    )
                )
            else:
                errors.append(
                    WorkingCopyCommitError(
                        row=row_idx,
                        reason=str(exc.content.get("detail") or "Błąd zapisu wiersza."),
                    )
                )
        except HTTPException as exc:
            errors.append(WorkingCopyCommitError(row=row_idx, reason=str(exc.detail)))

        refreshed_rows.append(row_copy)

    # Keep working copy until 24h TTL with refreshed case_id/version so user can download
    copy.rows_json = refreshed_rows
    db.commit()

    record_last_import_at(
        db=db,
        actor_id=actor.id,
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
    )
    db.commit()

    return WorkingCopyCommitResponse(
        created=created,
        updated=updated,
        skipped=skipped,
        conflicts=conflicts,
        errors=errors,
    )
