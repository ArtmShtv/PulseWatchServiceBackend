import logging

import redis

from app.core.config import settings
from app.ws.events import build_event, user_channel

logger = logging.getLogger(__name__)
_redis = redis.Redis.from_url(settings.REDIS_URL)

def publish_event(user_id: int, event_type: str, monitor_id: int, data: dict) -> None:
    try:
        _redis.publish(user_channel(user_id), build_event(event_type, monitor_id, data))
    except redis.RedisError:
        logger.warning("Failed to publish event", exc_info=True)