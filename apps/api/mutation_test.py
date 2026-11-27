"""
Windows-compatible Mutation Testing Runner for Malinois Backend.

Applies targeted security & business-logic mutations to core modules, runs the
focused pytest suite for each mutant, guarantees original source restoration in
`finally`, and reports the Mutation Score (% killed).

Usage:
    cd apps/api
    uv run python mutation_test.py
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

API_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Mutant:
    id: str
    file_rel: str
    description: str
    target: str
    replacement: str
    test_cmd: list[str]


MUTANTS: list[Mutant] = [
    Mutant(
        id="SEC-01",
        file_rel="security.py",
        description="Weaken min password length from 12 to 6",
        target="MIN_PASSWORD_LENGTH = 12",
        replacement="MIN_PASSWORD_LENGTH = 6",
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_penetration_security.py", "-k", "password_policy"],
    ),
    Mutant(
        id="SEC-02",
        file_rel="security.py",
        description="Disable >72-byte bcrypt length cap",
        target="MAX_PASSWORD_BYTES = 72",
        replacement="MAX_PASSWORD_BYTES = 999",
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_penetration_security.py", "-k", "password_policy"],
    ),
    Mutant(
        id="SEC-03",
        file_rel="security.py",
        description="Disable production default JWT secret guard",
        target='if env == "production" and (not secret or secret == DEFAULT_DEV_SECRET_KEY):',
        replacement='if False and env == "production" and (not secret or secret == DEFAULT_DEV_SECRET_KEY):',
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_penetration_security.py", "-k", "default_jwt_secret"],
    ),
    Mutant(
        id="SEC-04",
        file_rel="security.py",
        description="Raise login rate limit from 10 to 50 requests/min",
        target="LOGIN_RATE_LIMIT_MAX = 10",
        replacement="LOGIN_RATE_LIMIT_MAX = 50",
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_penetration_security.py", "-k", "rate_limited"],
    ),
    Mutant(
        id="BKP-01",
        file_rel="services/backups.py",
        description="Bypass FILENAME_PATTERN allowlist in validate_backup_filename",
        target="or not FILENAME_PATTERN.match(filename)",
        replacement="or False",
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_penetration_security.py", "-k", "path_traversal"],
    ),
    Mutant(
        id="BKP-02",
        file_rel="services/backups.py",
        description="Skip admin password verification on backup download",
        target="if not verify_password(password, actor.hashed_password):",
        replacement="if False:",
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_search_dashboard_bulk_reassign_backups.py", "-k", "automated_backups"],
    ),
    Mutant(
        id="RBAC-01",
        file_rel="services/cases.py",
        description="Allow regular user to bulk restore archived cases",
        target='if payload.action == "restore" and actor.role == "user":',
        replacement='if False and payload.action == "restore" and actor.role == "user":',
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_search_dashboard_bulk_reassign_backups.py", "-k", "bulk_operations"],
    ),
    Mutant(
        id="RBAC-02",
        file_rel="services/cases.py",
        description="Allow regular user to reassign cases",
        target='if actor.role == "user":\n        raise HTTPException(\n            status_code=status.HTTP_403_FORBIDDEN,\n            detail="Zwykły użytkownik nie może przepisywać spraw.",',
        replacement='if False:\n        raise HTTPException(\n            status_code=status.HTTP_403_FORBIDDEN,\n            detail="Zwykły użytkownik nie może przepisywać spraw.",',
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_search_dashboard_bulk_reassign_backups.py", "-k", "reassignment"],
    ),
    Mutant(
        id="DATE-01",
        file_rel="services/cases.py",
        description="Flip overdue comparison '< today' to '<= today' (today wrongly overdue)",
        target="Case.deadline < today,",
        replacement="Case.deadline <= today,",
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_edge_cases.py", "-k", "today_is_due_soon"],
    ),
    Mutant(
        id="PII-01",
        file_rel="services/audit.py",
        description="Remove 'pesel' from sensitive redaction tokens",
        target='_SENSITIVE_KEY_TOKENS = ("pesel", "password", "haslo")',
        replacement='_SENSITIVE_KEY_TOKENS = ("password", "haslo")',
        test_cmd=[sys.executable, "-m", "pytest", "-q", "-x", "tests/test_penetration_security.py", "-k", "pesel_redacted"],
    ),
]


def run_mutations() -> int:
    killed = 0
    survived: list[Mutant] = []

    print(f"Running {len(MUTANTS)} backend mutants...\n")
    for m in MUTANTS:
        path = API_DIR / m.file_rel
        original = path.read_text(encoding="utf-8")
        if m.target not in original:
            print(f"[SKIP]   {m.id}: target snippet not found in {m.file_rel}")
            continue

        mutated = original.replace(m.target, m.replacement, 1)
        try:
            path.write_text(mutated, encoding="utf-8")
            proc = subprocess.run(
                m.test_cmd,
                cwd=API_DIR,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            path.write_text(original, encoding="utf-8")

        if proc.returncode != 0:
            killed += 1
            print(f"[KILLED]   {m.id} ({m.file_rel}): {m.description}")
        else:
            survived.append(m)
            print(f"[SURVIVED] {m.id} ({m.file_rel}): {m.description}")

    total = killed + len(survived)
    score = (killed / total * 100.0) if total else 0.0
    print(f"\nBackend Mutation Score: {killed}/{total} killed ({score:.1f}%)")
    if survived:
        print("Survived mutants:")
        for s in survived:
            print(f"  - {s.id}: {s.description}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_mutations())
