from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.database import created_at, int_pk, updated_at

if TYPE_CHECKING:
    from app.db.models.monitor import Monitor


class User(Base):
    id: Mapped[int_pk]

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at: Mapped[created_at]
    updated_at: Mapped[updated_at]

    monitors: Mapped[list["Monitor"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )