from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlalchemy import select, update

from app.db.celery_session import CelerySession
from app.db.models.monitor import Monitor
from app.tasks.tasks import check_endpoint


@shared_task
def dispatch_due_monitors():
    with CelerySession() as session:
        now = datetime.now(UTC)

        stmt = (
            select(Monitor.id, Monitor.interval_seconds)
            .where(Monitor.is_active.is_(True))
            .where(Monitor.next_run_at <= now)
            .with_for_update(skip_locked=True)
        )
        due_monitors = session.execute(stmt).all()

        for monitor_id, interval_seconds in due_monitors:
            check_endpoint.delay(monitor_id)
            session.execute(
                update(Monitor)
                .where(Monitor.id == monitor_id)
                .values(next_run_at=now + timedelta(seconds=interval_seconds))
            )

        session.commit()