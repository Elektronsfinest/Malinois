# Monorepo: FastAPI + React (Logowanie i Dashboard)

## Struktura projektu
- `apps/api` — backend (FastAPI, SQLAlchemy 2.0+, Alembic, PostgreSQL, bcrypt, PyJWT)
- `apps/web` — frontend (React, TypeScript, Vite, `@tanstack/react-router`)
- `docker-compose.yml` — baza danych PostgreSQL 16

## Uruchomienie krok po kroku

### 1. Baza danych PostgreSQL
W katalogu głównym repozytorium uruchom kontener PostgreSQL (wymaga uruchomionego Docker Desktop):
```bash
docker compose up -d
```

Domyślne połączenie (zgodne z `docker-compose.yml`):
```text
postgresql+psycopg://malinois_user:malinois_password@localhost:5432/malinois_db
```
Możesz je nadpisać zmienną środowiskową `DATABASE_URL`.

### 2. Backend (`apps/api`)
Przejdź do katalogu backendu:
```bash
cd apps/api
```

Zainstaluj zależności (za pomocą `uv`):
```bash
uv sync
```

Uruchom migracje Alembic (utworzy tabelę `users` w bazie PostgreSQL):
```bash
uv run alembic upgrade head
```

Uruchom serwer FastAPI:
```bash
uv run uvicorn main:app --reload --port 8000
```

Przy pierwszym starcie aplikacja automatycznie doda testowego użytkownika (jeśli tabela `users` jest pusta):
- Email: `trainee@example.com`
- Hasło: `Secret123!`

Opcjonalnie można uruchomić seeder ręcznie:
```bash
uv run python seed.py
```

### 3. Frontend (`apps/web`)
W drugim terminalu przejdź do katalogu frontendu:
```bash
cd apps/web
```

Zainstaluj zależności:
```bash
npm install
```

Uruchom serwer deweloperski:
```bash
npm run dev
```

Aplikacja będzie dostępna pod adresem `http://localhost:5173`.
