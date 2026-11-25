"""
Emergency Event ORM model.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ambulance")
    stage1_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stage2_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signal_response: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EmergencyEvent id={self.id} direction={self.direction!r} "
            f"vehicle_type={self.vehicle_type!r} confirmed={self.stage2_confirmed}>"
        )
