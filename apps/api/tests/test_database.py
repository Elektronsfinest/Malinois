import inspect
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent


class TestUserModelAndSchema:
    def test_user_model_structure_and_columns(self):
        """Sprawdza model User (SQLAlchemy 2.0+): tabela 'users' i wymagane kolumny."""
        try:
            from sqlalchemy import inspect as sa_inspect
        except ImportError:
            pytest.fail("Brak zainstalowanego pakietu 'sqlalchemy' (wymagany SQLAlchemy 2.0+)")

        try:
            import models as models_module
        except ImportError:
            pytest.fail("Brak modułu 'models' z modelem User (Zadanie 2)")

        assert hasattr(models_module, "User"), "Moduł 'models' musi definiować klasę 'User'"
        User = models_module.User

        assert getattr(User, "__tablename__", None) == "users"

        mapper = sa_inspect(User)
        columns = {col.key: col for col in mapper.columns}

        assert "id" in columns, "Tabela 'users' musi posiadać kolumnę 'id'"
        assert columns["id"].primary_key is True, "Kolumna 'id' musi być kluczem głównym"

        assert "email" in columns, "Tabela 'users' musi posiadać kolumnę 'email'"
        assert columns["email"].unique is True or any(
            idx.unique and "email" in [c.name for c in idx.columns]
            for idx in User.__table__.indexes
        ), "Kolumna 'email' musi być unikalna"
        assert columns["email"].index is True or any(
            "email" in [c.name for c in idx.columns]
            for idx in User.__table__.indexes
        ), "Kolumna 'email' musi być indeksowana"

        assert "hashed_password" in columns, (
            "Tabela 'users' musi posiadać kolumnę 'hashed_password'"
        )
        assert "is_active" in columns, "Tabela 'users' musi posiadać kolumnę 'is_active'"
        is_active_col = columns["is_active"]
        has_true_default = (
            (is_active_col.default is not None and is_active_col.default.arg is True)
            or is_active_col.server_default is not None
        )
        assert has_true_default, "Kolumna 'is_active' musi mieć wartość domyślną True"


class TestDatabaseSessionManagement:
    def test_get_db_is_generator_and_closes_session(self):
        """Sprawdza czy get_db używa 'yield' i zamyka sesję po obsłużeniu zapytania."""
        try:
            import database as db_module
        except ImportError:
            pytest.fail("Brak modułu 'database' z konfiguracją SQLAlchemy (Zadanie 2)")

        assert hasattr(db_module, "get_db"), "Moduł 'database' musi udostępniać zależność 'get_db'"
        assert hasattr(db_module, "SessionLocal"), (
            "Moduł 'database' musi definiować 'SessionLocal'"
        )

        get_db = db_module.get_db
        assert inspect.isgeneratorfunction(get_db), (
            "Zależność 'get_db' musi być generatorem używającym instrukcji 'yield'"
        )

        gen = get_db()
        session = next(gen)
        assert session is not None
        with pytest.raises(StopIteration):
            next(gen)


class TestPasswordHashingAndSeeding:
    def test_password_is_hashed_and_not_plain_text(self):
        """Sprawdza czy hasło testowego użytkownika jest zahaszowane (bcrypt/argon2), a nie jawne."""
        try:
            import database as db_module
            import models as models_module
        except ImportError:
            pytest.fail("Brak modułów 'database' oraz 'models' (Zadanie 2)")

        User = models_module.User

        with db_module.SessionLocal() as db:
            user = db.query(User).filter(User.email == "trainee@example.com").first()
            assert user is not None, (
                "Użytkownik 'trainee@example.com' powinien istnieć w bazie (seeder)"
            )
            assert user.hashed_password != "Secret123!", (
                "Hasło w bazie danych NIE może być zapisane otwartym tekstem!"
            )
            assert len(user.hashed_password) > 20, (
                "Kolumna 'hashed_password' powinna zawierać poprawny hash (np. bcrypt/argon2)"
            )
            assert user.is_active is True


class TestAlembicMigrations:
    def test_alembic_directory_and_migration_files_exist(self):
        """Sprawdza czy Alembic został zainicjalizowany i zawiera wygenerowaną migrację."""
        alembic_ini = API_ROOT / "alembic.ini"
        alembic_dir = API_ROOT / "alembic"
        versions_dir = alembic_dir / "versions"
        env_py = alembic_dir / "env.py"

        assert alembic_ini.exists(), "Brak pliku 'alembic.ini' w katalogu backendu"
        assert alembic_dir.is_dir(), "Brak katalogu 'alembic/' w katalogu backendu"
        assert env_py.exists(), "Brak pliku 'alembic/env.py'"
        assert versions_dir.is_dir(), "Brak katalogu 'alembic/versions/'"

        migration_files = list(versions_dir.glob("*.py"))
        assert len(migration_files) >= 1, (
            "W katalogu 'alembic/versions/' musi znajdować się co najmniej jedna migracja tworząca tabelę 'users'"
        )

        env_content = env_py.read_text(encoding="utf-8")
        assert "target_metadata" in env_content and "target_metadata = None" not in env_content, (
            "Plik 'alembic/env.py' musi mieć skonfigurowane 'target_metadata' wskazujące na Base.metadata"
        )
