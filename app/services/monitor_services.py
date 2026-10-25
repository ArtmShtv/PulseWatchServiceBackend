import logging
import smtplib
from collections.abc import Sequence
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    InvalidMonitorDataError,
    MonitorAlreadyExistsError,
    MonitorNotFoundError,
)
from app.db.models.monitor import Monitor
from app.db.models.user import User
from app.schemas.monitor_schemas import MonitorCreateSchema, MonitorUpdateSchema

logger = logging.getLogger(__name__)

# Changing any of these means the next check should run right away
_RESCHEDULE_FIELDS = {"url", "method", "interval_seconds", "timeout_seconds", "expected_status"}


async def get_user_monitor(
    session: AsyncSession,
    monitor_id: int,
    current_user: User,
) -> Monitor:
    monitor = await session.scalar(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == current_user.id,
        )
    )
    if monitor is None:
        raise MonitorNotFoundError("Monitor not found")
    return monitor


async def list_user_monitors(
    session: AsyncSession,
    current_user: User,
) -> Sequence[Monitor]:
    result = await session.scalars(
        select(Monitor)
        .where(Monitor.user_id == current_user.id)
        .order_by(Monitor.id)
    )
    return result.all()


async def create_monitor(
    session: AsyncSession,
    monitor_data: MonitorCreateSchema,
    current_user: User,
) -> Monitor:
    monitor = Monitor(
        user_id=current_user.id,
        name=monitor_data.name,
        url=str(monitor_data.url),
        method=monitor_data.method,
        interval_seconds=monitor_data.interval_seconds,
        timeout_seconds=monitor_data.timeout_seconds,
        expected_status=monitor_data.expected_status,
        next_run_at=datetime.now(UTC),  # first check runs right away
    )
    session.add(monitor)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise MonitorAlreadyExistsError(
            "Monitor with this URL and method already exists"
        ) from None

    await session.refresh(monitor)
    return monitor


async def update_monitor(
    session: AsyncSession,
    monitor_id: int,
    monitor_data: MonitorUpdateSchema,
    current_user: User,
) -> Monitor:
    monitor = await get_user_monitor(session, monitor_id, current_user)

    # mode="json" turns HttpUrl into str; exclude_none ignores explicit nulls
    changes = monitor_data.model_dump(exclude_unset=True, exclude_none=True, mode="json")
    if not changes:
        raise InvalidMonitorDataError("No fields to update")

    # Validate against the merged state, not only the fields that were sent
    interval = changes.get("interval_seconds", monitor.interval_seconds)
    timeout = changes.get("timeout_seconds", monitor.timeout_seconds)
    if timeout >= interval:
        raise InvalidMonitorDataError("timeout_seconds must be less than interval_seconds")

    for field, value in changes.items():
        setattr(monitor, field, value)

    if _RESCHEDULE_FIELDS & changes.keys():
        monitor.next_run_at = datetime.now(UTC)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise MonitorAlreadyExistsError(
            "Monitor with this URL and method already exists"
        ) from None

    await session.refresh(monitor)
    return monitor


async def delete_monitor(
    session: AsyncSession,
    monitor_id: int,
    current_user: User,
) -> None:
    monitor = await get_user_monitor(session, monitor_id, current_user)
    await session.delete(monitor)
    await session.commit()


def send_email(receiver_email, subject, body):
    message = EmailMessage()
    message["From"] = f"PulseWatch <{settings.SENDER_EMAIL}>"
    message["To"] = receiver_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(settings.SENDER_EMAIL, settings.EMAIL_PASSWORD)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed — check SENDER_EMAIL/EMAIL_PASSWORD")
        raise
    except smtplib.SMTPException:
        logger.exception("SMTP error while sending email")
        raise
