from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from datetime import datetime, timedelta, timezone

from app.schemas.monitor_schemas import MonitorCreateSchema, MonitorUpdateSchema
from app.db.models.monitor import Monitor
from app.core.config import settings

import smtplib
from email.message import EmailMessage

import logging

logger = logging.getLogger(__name__)


async def create_monitor(
    session: AsyncSession,
    monitor_data: MonitorCreateSchema,
    current_user
) -> Monitor:
    result = await session.execute(
        select(Monitor).where(
            (Monitor.user_id == current_user.id) &
            (Monitor.url == monitor_data.url) &
            (Monitor.method == monitor_data.method)
        )
    )

    existing_monitor = result.scalar_one_or_none()
    if existing_monitor:
        raise ValueError("Such monitor already exists")

    monitor = Monitor(
        user_id = current_user.id,
        name = monitor_data.name,
        url = monitor_data.url,
        method = monitor_data.method,
        interval_seconds = monitor_data.interval_seconds,
        timeout_seconds = monitor_data.timeout_seconds,
        expected_status = monitor_data.expected_status,
        next_run_at = datetime.now(timezone.utc) + timedelta(seconds=monitor_data.interval_seconds)
    )

    session.add(monitor)
    await session.commit()
    await session.refresh(monitor)

    return monitor


async def update_monitor(
    session: AsyncSession,
    monitor_id: int,
    monitor_data: MonitorUpdateSchema,
    current_user
) -> Monitor:

    result = await session.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == current_user.id
        )
    )
    monitor = result.scalar_one_or_none()

    if not monitor:
        raise ValueError("Such monitor doesn't exists")
    
    monitor_data_dict = monitor_data.model_dump(exclude_unset=True)

    for field, value in monitor_data_dict.items():
        setattr(monitor, field, value)

    await session.commit()
    await session.refresh(monitor)

    return monitor


async def delete_monitor(
    session: AsyncSession,
    monitor_id: int,
    current_user
) -> None:

    result = await session.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == current_user.id
        )
    )
    monitor = result.scalar_one_or_none()

    if not monitor:
        raise ValueError("Such monitor doesn't exists")

    await session.delete(monitor)
    await session.commit()

    return


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