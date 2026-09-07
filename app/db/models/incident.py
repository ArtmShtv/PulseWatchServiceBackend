from datetime import datetime

from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.database import int_pk

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.monitor import Monitor


class IncidentStatus(StrEnum):
    ONGOING = "ONGOING"
    RESOLVED = "RESOLVED"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int_pk]
    monitor_id: Mapped[int] = mapped_column(
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    monitor: Mapped["Monitor"] = relationship(
        back_populates="incidents",
    )