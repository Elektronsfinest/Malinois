import asyncio
from contextlib import asynccontextmanager, suppress
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from exceptions import StructuredHTTPException
from routers.admin_users import router as admin_users_router
from routers.auth import router as auth_router
from routers.backups import router as backups_router
from routers.cases import router as cases_router
from routers.dashboard import router as dashboard_router
from routers.history_notes import router as history_notes_router
from routers.import_copies import router as import_copies_router
from routers.notifications import router as notifications_router
from security import validate_jwt_secret
from seed import ensure_seeded
from services.backups import nightly_backup_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_jwt_secret()
    ensure_seeded()
    scheduler_task: asyncio.Task[None] | None = None
    env_name = os.getenv("ENV", "development").strip().lower()
    if env_name != "test" and not os.getenv("PYTEST_CURRENT_TEST"):
        scheduler_task = asyncio.create_task(nightly_backup_loop())
    try:
        yield
    finally:
        if scheduler_task is not None:
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task


app = FastAPI(lifespan=lifespan)


@app.exception_handler(StructuredHTTPException)
async def structured_http_exception_handler(
    _: Request, exc: StructuredHTTPException
) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.content)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(backups_router)
app.include_router(cases_router)
app.include_router(dashboard_router)
app.include_router(history_notes_router)
app.include_router(import_copies_router)
app.include_router(notifications_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health")
async def health():
    return {"status": "ok"}
