"""
Camera ORM model.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unique_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    direction: Mapped[str] = mapped_column(
        Enum("north", "south", "east", "west", name="camera_direction"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("online", "offline", "connecting", "error", name="camera_status"),
        nullable=False,
        default="offline",
    )
    stream_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Camera id={self.id} direction={self.direction!r} status={self.status!r}>"
