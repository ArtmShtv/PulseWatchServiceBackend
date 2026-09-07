from datetime import datetime, timezone

import requests
from celery import shared_task
from celery.utils.log import get_task_logger

from app.db.celery_session import CelerySession
from app.db.models.monitor import Monitor, MonitorStatus
from app.db.models.monitor_check import MonitorCheck
from app.db.models.incident import Incident, IncidentStatus

logger = get_task_logger(__name__)


@shared_task
def check_endpoint(monitor_id: int):
    with CelerySession() as session:
        monitor = session.get(Monitor, monitor_id)
        if monitor is None:
            return

        checked_at = datetime.now(timezone.utc)

        try:
            response = requests.request(
                monitor.method,
                monitor.url,
                timeout=monitor.timeout_seconds,
            )
            response_ms = round(response.elapsed.total_seconds() * 1000)
            status_code = response.status_code

            if status_code == monitor.expected_status:
                is_up = True
                failure_reason = None
            else:
                is_up = False
                failure_reason = f"Server returned {status_code} instead of {monitor.expected_status}"

        except requests.RequestException as e:
            logger.warning(f"Check failed for {monitor.name} ({monitor.url}): {e}")
            response_ms = None
            status_code = None
            is_up = False
            failure_reason = str(e)

        current_status = MonitorStatus.UP if is_up else MonitorStatus.DOWN

        check = MonitorCheck(
            monitor_id=monitor_id,
            status=current_status,
            status_code=status_code,
            response_ms=response_ms,
            checked_at=checked_at,
            error_message=failure_reason,
        )
        session.add(check)

        monitor.last_checked_at = checked_at
        monitor.last_response_ms = response_ms

        was_down = monitor.current_status == MonitorStatus.DOWN

        if not is_up and not was_down:
            incident = Incident(
                monitor_id=monitor_id,
                started_at=checked_at,
                status=IncidentStatus.ONGOING,
                reason=failure_reason,
            )
            session.add(incident)
            monitor.current_status = MonitorStatus.DOWN

        elif is_up and was_down:
            ongoing = (
                session.query(Incident)
                .filter(
                    Incident.monitor_id == monitor_id,
                    Incident.status == IncidentStatus.ONGOING,
                )
                .first()
            )
            if ongoing:
                ongoing.status = IncidentStatus.RESOLVED
                ongoing.resolved_at = checked_at
            monitor.current_status = MonitorStatus.UP

        else:
            monitor.current_status = current_status

        session.commit()