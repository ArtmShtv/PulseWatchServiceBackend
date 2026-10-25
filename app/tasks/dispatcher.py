from datetime import UTC, datetime, timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import Interval, literal, select, update

from app.db.celery_session import CelerySession
from app.db.models.monitor import Monitor
from app.tasks.tasks import check_endpoint

logger = get_task_logger(__name__)

BATCH_SIZE = 500
ONE_SECOND = literal(timedelta(seconds=1), Interval)


@shared_task(ignore_result=True)
def dispatch_due_monitors() -> int:
    now = datetime.now(UTC)

    due_ids = (
        select(Monitor.id)
        .where(Monitor.is_active.is_(True), Monitor.next_run_at <= now)
        .order_by(Monitor.next_run_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )

    stmt = (
        update(Monitor)
        .where(Monitor.id.in_(due_ids.scalar_subquery()))
        .values(next_run_at=now + Monitor.interval_seconds * ONE_SECOND)
        .returning(Monitor.id, Monitor.interval_seconds)
    )

    with CelerySession() as session:
        scheduled = session.execute(stmt).all()
        session.commit()

    for monitor_id, interval_seconds in scheduled:
        check_endpoint.apply_async((monitor_id,), expires=interval_seconds)

    if len(scheduled) == BATCH_SIZE:
        logger.warning("Dispatched a full batch of %s monitors; workers may be falling behind", BATCH_SIZE)

    return len(scheduled)