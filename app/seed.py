from __future__ import annotations

import os
from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Role, User
from .security import hash_password


def main() -> None:
    Base.metadata.create_all(bind=engine)
    username = os.getenv("DEMO_ADMIN_USERNAME", "demo")
    password = os.getenv("DEMO_ADMIN_PASSWORD", "demo12345")
    email = os.getenv("DEMO_ADMIN_EMAIL", "demo@example.com")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)):
            return
        db.add(User(username=username, display_name="Demo Admin", email=email, password_hash=hash_password(password), role=Role.admin))
        db.commit()


if __name__ == "__main__":
    main()
