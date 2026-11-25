"""Create or update initial administrator user in the database."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from core.database import db_session, init_db  # noqa: E402
from core.security import hash_password  # noqa: E402
from models.user import User  # noqa: E402


async def main() -> None:
    await init_db()
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@smarttraffic.local")
    password = os.getenv("ADMIN_PASSWORD", "Admin@12345")

    async with db_session() as db:
        existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = "admin"
            existing.is_active = True
            print(f"Updated existing admin user '{username}'.")
        else:
            db.add(
                User(
                    username=username,
                    email=email,
                    hashed_password=hash_password(password),
                    role="admin",
                    is_active=True,
                )
            )
            print(f"Created admin user '{username}' ({email}).")


if __name__ == "__main__":
    asyncio.run(main())
