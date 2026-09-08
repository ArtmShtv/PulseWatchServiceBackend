import os

from celery import Celery


celery_app = Celery(
    "pulsewatch",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
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
        "schedule": 10.0,
    },
}
celery_app.conf.timezone = "UTC"