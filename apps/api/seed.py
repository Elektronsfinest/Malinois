from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import User
from security import hash_password


def seed_initial_user(db: Session) -> None:
    existing_user = db.scalar(select(User).limit(1))
    if existing_user is not None:
        return

    user = User(
        email="trainee@example.com",
        hashed_password=hash_password("Secret123!"),
        is_active=True,
    )
    db.add(user)
    db.commit()


def ensure_seeded() -> None:
    if not inspect(engine).has_table("users"):
        return

    db = SessionLocal()
    try:
        seed_initial_user(db)
    finally:
        db.close()


if __name__ == "__main__":
    ensure_seeded()
