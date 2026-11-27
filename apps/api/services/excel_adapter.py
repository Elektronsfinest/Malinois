from datetime import date, datetime
import io
import re
from typing import Any
from fastapi import HTTPException, status
import openpyxl
import xlrd

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/msexcel",
    "application/x-msexcel",
    "application/x-excel",
    "application/x-dos_ms_excel",
    "application/xls",
    "application/x-xls",
}

HEADER_ALIASES: dict[str, str] = {
    "numer e2": "case_number",
    "nr sprawy": "case_number",
    "numer sprawy": "case_number",
    "case number": "case_number",
    "case_number": "case_number",
    "tytuł": "title",
    "tytul": "title",
    "title": "title",
    "dane": "client_name",
    "klient": "client_name",
    "client": "client_name",
    "client_name": "client_name",
    "przypisany": "assigned_to_email",
    "assigned to": "assigned_to_email",
    "assigned_to": "assigned_to_email",
    "email": "assigned_to_email",
    "termin realizacji": "deadline",
    "termin": "deadline",
    "deadline": "deadline",
    "data wpływu epwd": "date_filed_epwd",
    "data wplywu epwd": "date_filed_epwd",
    "data złożenia": "date_filed",
    "data zlozenia": "date_filed",
    "date filed": "date_filed",
    "date_filed": "date_filed",
    "status": "status",
    "uwagi": "note",
    "notatka": "note",
    "note": "note",
}

_LEADING_DATE_RE = re.compile(
    r"^\s*(\d{2}[.-]\d{2}[.-]\d{4}|\d{4}-\d{2}-\d{2})(?:\s*[-–—]?\s*(.*))?$"
)
_DATE_LIKE_RE = re.compile(r"^\s*(\d{1,2}[.-]\d{1,2}[.-]\d{2,4}|\d{4}[.-]\d{1,2}[.-]\d{1,2})\s*$")


def sanitize_label(filename: str | None) -> str:
    if not filename:
        return "import.xlsx"
    # Never use in filesystem operations; display label only
    base = filename.replace("\\", "/").split("/")[-1].strip()
    return (base or "import.xlsx")[:255]


def validate_upload_file(filename: str | None, content_type: str | None, raw_bytes: bytes) -> str:
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Plik przekracza maksymalny dozwolony rozmiar 10 MB.",
        )
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Przesłany plik jest pusty.",
        )

    lower_name = (filename or "").lower().strip()
    ext = ""
    if lower_name.endswith(".xlsx"):
        ext = ".xlsx"
    elif lower_name.endswith(".xls"):
        ext = ".xls"

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieobsługiwane rozszerzenie pliku. Dozwolone są wyłącznie pliki .xlsx oraz .xls.",
        )

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy typ MIME pliku Excel.",
        )

    return ext


def _stringify_cell(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def _parse_single_date_str(text: str) -> date | None:
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_date_value(
    value: Any, *, allow_free_text_warning: bool = False
) -> tuple[str | None, str | None, str | None]:
    """Returns (iso_date, blocking_error, non_blocking_warning)."""
    if value is None:
        return None, None, None
    if isinstance(value, datetime):
        return value.date().isoformat(), None, None
    if isinstance(value, date):
        return value.isoformat(), None, None

    text = str(value).strip()
    if not text:
        return None, None, None

    parsed = _parse_single_date_str(text)
    if parsed is not None:
        return parsed.isoformat(), None, None

    if allow_free_text_warning and not _DATE_LIKE_RE.match(text):
        return (
            None,
            None,
            f"Termin realizacji zawiera tekst („{text}”) zamiast daty — zachowano w polach dodatkowych.",
        )

    return None, f"Niepoprawny format daty: „{text}” (oczekiwano DD.MM.YYYY, DD-MM-YYYY lub YYYY-MM-DD).", None


def parse_epwd_value(value: Any) -> tuple[str | None, str | None, str | None, str | None]:
    """Parses ZUS DATA WPŁYWU EPWD.
    Returns (iso_date, suffix_text, raw_text, blocking_error).
    """
    if value is None:
        return None, None, None, None
    if isinstance(value, datetime):
        d = value.date()
        return d.isoformat(), None, d.strftime("%d.%m.%Y"), None
    if isinstance(value, date):
        return value.isoformat(), None, value.strftime("%d.%m.%Y"), None

    raw = str(value).strip()
    if not raw:
        return None, None, None, None

    m = _LEADING_DATE_RE.match(raw)
    if m:
        date_part = m.group(1)
        suffix = (m.group(2) or "").strip() or None
        parsed = _parse_single_date_str(date_part)
        if parsed is None:
            return None, suffix, raw, f"Niepoprawna data wpływu EPWD: „{date_part}”."
        return parsed.isoformat(), suffix, raw, None

    # Pure text entry (e.g. "z urzędu - EDUK") is valid in ZUS workbooks
    return None, raw, raw, None


def _normalize_status(raw: str | None) -> str:
    if not raw:
        return "open"
    low = raw.strip().lower()
    if low in ("closed", "zamknięta", "zamknieta", "zakończona", "zakonczona", "zakończono"):
        return "closed"
    return "open"


def _read_raw_rows(ext: str, raw_bytes: bytes) -> tuple[list[str], list[list[Any]]]:
    try:
        if ext == ".xlsx":
            wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True, read_only=True)
            ws = wb.active
            if ws is None:
                return [], []
            raw_rows = [list(r) for r in ws.iter_rows(values_only=True)]
            wb.close()
        else:
            wb = xlrd.open_workbook(file_contents=raw_bytes)
            if wb.nsheets == 0:
                return [], []
            sheet = wb.sheet_by_index(0)
            raw_rows = []
            for r_idx in range(sheet.nrows):
                row_vals: list[Any] = []
                for c_idx in range(sheet.ncols):
                    cell = sheet.cell(r_idx, c_idx)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        dt_tuple = xlrd.xldate_as_tuple(cell.value, wb.datemode)
                        row_vals.append(date(dt_tuple[0], dt_tuple[1], dt_tuple[2]))
                    else:
                        row_vals.append(cell.value)
                raw_rows.append(row_vals)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nie udało się odczytać pliku Excel. Sprawdź, czy plik nie jest uszkodzony.",
        ) from exc

    if not raw_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arkusz Excel nie zawiera żadnych wierszy.",
        )

    raw_headers = raw_rows[0]
    headers: list[str] = []
    seen_exact: dict[str, int] = {}
    for idx, h in enumerate(raw_headers):
        label = str(h).strip() if h is not None and str(h).strip() else f"Kolumna_{idx + 1}"
        if label in seen_exact:
            seen_exact[label] += 1
            label = f"{label} ({seen_exact[label]})"
        else:
            seen_exact[label] = 1
        headers.append(label)

    return headers, raw_rows[1:]


def parse_excel_bytes(
    *,
    filename: str | None,
    content_type: str | None,
    raw_bytes: bytes,
    default_assigned_to_email: str | None = None,
) -> list[dict[str, Any]]:
    ext = validate_upload_file(filename, content_type, raw_bytes)
    headers, data_rows = _read_raw_rows(ext, raw_bytes)

    mapped_indices: dict[int, tuple[str, str]] = {}
    for idx, header in enumerate(headers):
        canonical = HEADER_ALIASES.get(header.strip().lower())
        if canonical is not None:
            mapped_indices[idx] = (canonical, header)

    parsed_rows: list[dict[str, Any]] = []
    for offset, row_vals in enumerate(data_rows, start=2):
        # Skip completely empty rows
        if not any(v is not None and str(v).strip() != "" for v in row_vals):
            continue

        row_dict: dict[str, Any] = {
            "row_index": offset,
            "case_id": None,
            "version": None,
            "case_number": None,
            "title": None,
            "client_name": None,
            "assigned_to_email": default_assigned_to_email,
            "deadline": None,
            "date_filed": None,
            "status": "open",
            "note": None,
            "extra_columns": {},
            "errors": [],
            "warnings": [],
            "conflict": False,
            "resolution": None,
        }

        epwd_suffix: str | None = None

        for idx, header in enumerate(headers):
            val = row_vals[idx] if idx < len(row_vals) else None
            if idx in mapped_indices:
                canonical, orig_header = mapped_indices[idx]
                if canonical == "case_number":
                    row_dict["case_number"] = _stringify_cell(val)
                elif canonical == "title":
                    row_dict["title"] = _stringify_cell(val)
                elif canonical == "client_name":
                    row_dict["client_name"] = _stringify_cell(val)
                elif canonical == "assigned_to_email":
                    email_val = _stringify_cell(val)
                    if email_val:
                        row_dict["assigned_to_email"] = email_val.lower()
                elif canonical == "deadline":
                    iso_d, err, warn = parse_date_value(val, allow_free_text_warning=True)
                    row_dict["deadline"] = iso_d
                    if err:
                        row_dict["errors"].append(err)
                    if warn:
                        row_dict["warnings"].append(warn)
                        row_dict["extra_columns"][orig_header] = _stringify_cell(val)
                elif canonical == "date_filed_epwd":
                    iso_d, suffix, raw_txt, err = parse_epwd_value(val)
                    row_dict["date_filed"] = iso_d
                    epwd_suffix = suffix
                    if raw_txt is not None:
                        row_dict["extra_columns"][orig_header] = raw_txt
                    if err:
                        row_dict["errors"].append(err)
                elif canonical == "date_filed":
                    iso_d, err, _ = parse_date_value(val, allow_free_text_warning=False)
                    row_dict["date_filed"] = iso_d
                    if err:
                        row_dict["errors"].append(err)
                elif canonical == "status":
                    raw_status = _stringify_cell(val)
                    row_dict["status"] = _normalize_status(raw_status)
                    if raw_status and raw_status.lower() not in ("open", "closed", "otwarta", "zamknięta"):
                        row_dict["extra_columns"][orig_header] = raw_status
                elif canonical == "note":
                    row_dict["note"] = _stringify_cell(val)
            else:
                # Preserve all unmapped ZUS columns verbatim
                text_val = _stringify_cell(val)
                if text_val is not None:
                    row_dict["extra_columns"][header] = text_val

        # Auto-derive title when Tytuł column is absent (e.g. real ZUS workbook)
        if not row_dict["title"]:
            client_part = row_dict["client_name"] or ""
            if epwd_suffix and client_part:
                row_dict["title"] = f"{epwd_suffix} – {client_part}"[:255]
            elif row_dict["case_number"] and client_part:
                row_dict["title"] = f"Sprawa {row_dict['case_number']} – {client_part}"[:255]
            elif client_part:
                row_dict["title"] = f"Sprawa – {client_part}"[:255]

        parsed_rows.append(row_dict)

    return parsed_rows


def build_xlsx_bytes(rows: list[dict[str, Any]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Sprawy"

    extra_keys: list[str] = []
    seen_extra: set[str] = set()
    for r in rows:
        for k in (r.get("extra_columns") or {}).keys():
            if k not in seen_extra:
                seen_extra.add(k)
                extra_keys.append(k)

    core_headers = [
        "Nr sprawy",
        "Tytuł",
        "Klient",
        "Przypisany",
        "Termin",
        "Data złożenia",
        "Status",
        "Uwagi",
    ]
    ws.append(core_headers + extra_keys)

    def _fmt_iso(iso_val: str | None) -> str:
        if not iso_val:
            return ""
        parts = iso_val.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        return iso_val

    for r in rows:
        extra = r.get("extra_columns") or {}
        row_out = [
            r.get("case_number") or "",
            r.get("title") or "",
            r.get("client_name") or "",
            r.get("assigned_to_email") or "",
            _fmt_iso(r.get("deadline")),
            _fmt_iso(r.get("date_filed")),
            r.get("status") or "open",
            r.get("note") or "",
        ] + [extra.get(k) or "" for k in extra_keys]
        ws.append(row_out)

    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()
