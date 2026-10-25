import json
from datetime import UTC, datetime
from enum import StrEnum

USER_CHANNEL_PATTERN = "user:*:events"


class EventType(StrEnum):
    CONNECTED = "connected"
    PING = "ping"
    CHECK_COMPLETED = "check.completed"
    INCIDENT_OPENED = "incident.opened"
    INCIDENT_RESOLVED = "incident.resolved"


def user_channel(user_id: int) -> str:
    return f"user:{user_id}:events"


def parse_user_id(channel: str) -> int:
    return int(channel.split(":")[1])


def build_event(event_type: str, monitor_id: int | None = None, data: dict | None = None) -> str:
    return json.dumps({
        "type": event_type,
        "monitor_id": monitor_id,
        "ts": datetime.now(UTC).isoformat(),
        "data": data or {},
    })