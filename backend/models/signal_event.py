"""
Signal Event ORM model.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SignalEvent(Base):
    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    triggered_by: Mapped[str] = mapped_column(String(24), nullable=False, default="auto")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="AUTO")

    def __repr__(self) -> str:
        return (
            f"<SignalEvent id={self.id} direction={self.direction!r} "
            f"phase={self.phase!r} triggered_by={self.triggered_by!r}>"
        )
