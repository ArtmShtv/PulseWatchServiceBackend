import os

from celery import Celery


celery_app = Celery(
    "pulsewatch",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    include=["app.tasks.tasks", "app.tasks.dispatcher"],
)

celery_app.conf.beat_schedule = {
    "dispatch-due-monitors": {
        "task": "app.tasks.dispatcher.dispatch_due_monitors",
        "schedule": 10.0,
    },
}
celery_app.conf.timezone = "UTC"