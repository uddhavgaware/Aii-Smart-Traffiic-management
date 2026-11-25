"""
Traffic Event ORM model.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class TrafficEvent(Base):
    __tablename__ = "traffic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    vehicle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    density_level: Mapped[str] = mapped_column(String(24), nullable=False, default="LOW")
    speed_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    queue_length: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    congestion_predicted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<TrafficEvent id={self.id} direction={self.direction!r} "
            f"density={self.density_level!r}>"
        )
