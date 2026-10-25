
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "pulsewatch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.dispatcher",
        "app.tasks.tasks",
    ],
)

celery_app.conf.task_routes = {
    "app.tasks.dispatcher.dispatch_due_monitors": {"queue": "monitors"},
    "app.tasks.tasks.check_endpoint": {"queue": "monitors"},
    "app.tasks.tasks.send_incident_email": {"queue": "emails"},
}

celery_app.conf.beat_schedule = {
    "dispatch-due-monitors": {
        "task": "app.tasks.dispatcher.dispatch_due_monitors",
        "schedule": 1.0,
    },
}
celery_app.conf.timezone = "UTC"