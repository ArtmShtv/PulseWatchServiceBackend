import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin

import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.url_safety import UnsafeTargetError, ensure_public_target
from app.db.celery_session import CelerySession
from app.db.models.incident import Incident, IncidentStatus
from app.db.models.monitor import Monitor, MonitorStatus
from app.db.models.monitor_check import MonitorCheck
from app.services.event_publisher import publish_event
from app.services.monitor_services import send_email
from app.ws.events import EventType

logger = get_task_logger(__name__)

USER_AGENT = "PulseWatch/1.0"
CONFIRM_DELAY_SECONDS = 2
MAX_ERROR_LEN = 255
MAX_REDIRECTS = 5


@dataclass(frozen=True, slots=True)
class ProbeResult:
    is_up: bool
    status_code: int | None = None
    response_ms: int | None = None
    error: str | None = None


def _truncate(text: str | None, limit: int = MAX_ERROR_LEN) -> str | None:
    return text[:limit] if text else None


def _request_status(method: str, url: str, timeout: int) -> int:
    """Send the request and return the final status code.

    Redirects are followed manually so every hop is checked against SSRF rules:
    a public URL must not be able to redirect the worker into the private network.
    """
    for _ in range(MAX_REDIRECTS + 1):
        ensure_public_target(url)
        with requests.request(
            method,
            url,
            timeout=timeout,
            stream=True,  # only the status is needed, don't download the body
            allow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        ) as response:
            if not response.is_redirect:
                return response.status_code
            url = urljoin(url, response.headers["Location"])
    raise requests.TooManyRedirects(f"More than {MAX_REDIRECTS} redirects")


def probe(method: str, url: str, timeout: int, expected_status: int) -> ProbeResult:
    """Run a single HTTP check. No DB access, so it is easy to unit-test."""
    started = time.perf_counter()
    try:
        status_code = _request_status(method, url, timeout)
        response_ms = round((time.perf_counter() - started) * 1000)
    except UnsafeTargetError as e:
        return ProbeResult(False, error=f"Blocked: {e}")
    except socket.gaierror:
        return ProbeResult(False, error="DNS resolution failed")
    except requests.Timeout:
        return ProbeResult(False, error=f"Timed out after {timeout}s")
    except requests.exceptions.SSLError:
        return ProbeResult(False, error="SSL certificate error")
    except requests.ConnectionError:
        return ProbeResult(False, error="Connection failed")
    except requests.RequestException as e:
        return ProbeResult(False, error=f"Request error: {type(e).__name__}")

    if status_code == expected_status:
        return ProbeResult(True, status_code, response_ms)
    return ProbeResult(
        False,
        status_code,
        response_ms,
        f"Expected {expected_status}, got {status_code}",
    )


def apply_result(
    session: Session,
    monitor: Monitor,
    result: ProbeResult,
    checked_at: datetime,
) -> tuple[EventType | None, int | None]:
    new_status = MonitorStatus.UP if result.is_up else MonitorStatus.DOWN
    previous = monitor.current_status

    session.add(
        MonitorCheck(
            monitor_id=monitor.id,
            status=new_status,
            status_code=result.status_code,
            response_ms=result.response_ms,
            error_message=_truncate(result.error),
            checked_at=checked_at,
        )
    )
    monitor.last_checked_at = checked_at
    monitor.last_response_ms = result.response_ms
    monitor.current_status = new_status

    if new_status == MonitorStatus.DOWN and previous != MonitorStatus.DOWN:
        incident = Incident(
            monitor_id=monitor.id,
            started_at=checked_at,
            status=IncidentStatus.ONGOING,
            reason=_truncate(result.error),
        )
        session.add(incident)
        session.flush()
        return EventType.INCIDENT_OPENED, incident.id

    if new_status == MonitorStatus.UP and previous == MonitorStatus.DOWN:
        incident = session.scalars(
            select(Incident).where(
                Incident.monitor_id == monitor.id,
                Incident.status == IncidentStatus.ONGOING,
            )
        ).first()
        if incident:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = checked_at
        return EventType.INCIDENT_RESOLVED, incident.id if incident else None

    return None, None


@shared_task(ignore_result=True)
def check_endpoint(monitor_id: int) -> None:
    with CelerySession() as session:
        monitor = session.get(Monitor, monitor_id)
        if monitor is None or not monitor.is_active:
            return
        target = (
            monitor.method,
            monitor.url,
            monitor.timeout_seconds,
            monitor.expected_status,
        )
        name = monitor.name

    result = probe(*target)
    if not result.is_up:
        time.sleep(CONFIRM_DELAY_SECONDS)
        result = probe(*target)
        if not result.is_up:
            logger.warning("Check failed for %s (%s): %s", name, target[1], result.error)

    checked_at = datetime.now(UTC)

    with CelerySession() as session:
        monitor = session.scalars(
            select(Monitor).where(Monitor.id == monitor_id).with_for_update()
        ).one_or_none()
        if monitor is None:
            return
        transition, incident_id = apply_result(session, monitor, result, checked_at)
        user_id = monitor.user_id
        session.commit()

    publish_event(
        user_id,
        EventType.CHECK_COMPLETED,
        monitor_id,
        {
            "status": MonitorStatus.UP if result.is_up else MonitorStatus.DOWN,
            "status_code": result.status_code,
            "response_ms": result.response_ms,
            "checked_at": checked_at.isoformat(),
        },
    )
    if transition is not None:
        publish_event(
            user_id,
            transition,
            monitor_id,
            {"incident_id": incident_id, "reason": result.error},
        )
    if transition == EventType.INCIDENT_OPENED:
        send_incident_email.delay(incident_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def send_incident_email(self, incident_id: int) -> None:
    with CelerySession() as session:
        incident = session.get(Incident, incident_id)
        if incident is None:
            return

        monitor = incident.monitor
        user = monitor.user

        try:
            send_email(
                receiver_email=user.email,
                subject=f"Incident: {monitor.name} is down",
                body=f"{monitor.url} — {incident.reason}",
            )
        except Exception as e:
            logger.warning("Failed to send incident email %s: %s", incident_id, e)
            raise self.retry(exc=e) from e
