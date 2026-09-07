from datetime import datetime

from enum import StrEnum

from sqlalchemy import (
    Boolean, 
    DateTime, 
    ForeignKey, 
    Integer, 
    String, 
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.database import int_pk, created_at, updated_at

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.incident import Incident
    from app.db.models.monitor_check import MonitorCheck
    from app.db.models.user import User


class MonitorStatus(StrEnum):
    UP = "UP"
    DOWN = "DOWN"


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="GET"
    )
    interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10
    )
    expected_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=200
    )

    current_status: Mapped[MonitorStatus | None] = mapped_column(
        Enum(MonitorStatus),
        nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_response_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    user: Mapped["User"] = relationship(
        back_populates="monitors",
    )
    checks: Mapped[list["MonitorCheck"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
    )
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "url", "method"),
    )