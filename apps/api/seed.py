import os
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import User
from security import hash_password


def is_demo_seeding_enabled() -> bool:
    env = os.getenv("ENV", "development").lower()
    seed_flag = os.getenv("SEED_DEMO_USER", "").lower()
    if seed_flag in ("false", "0", "no"):
        return False
    if seed_flag in ("true", "1", "yes"):
        return True
    return env in ("development", "dev", "local", "test")


def seed_initial_user(db: Session) -> None:
    demo_email = "trainee@example.com"
    existing_user = db.scalar(select(User).where(User.email == demo_email))
    if existing_user is not None:
        return

    user = User(
        email=demo_email,
        hashed_password=hash_password("Secret123!"),
        is_active=True,
    )
    db.add(user)
    db.commit()


def ensure_seeded() -> None:
    if not is_demo_seeding_enabled():
        return

    if not inspect(engine).has_table("users"):
        return

    db = SessionLocal()
    try:
        seed_initial_user(db)
    finally:
        db.close()


if __name__ == "__main__":
    ensure_seeded()
