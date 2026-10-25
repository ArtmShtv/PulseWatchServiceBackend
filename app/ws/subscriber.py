import asyncio
import logging
from contextlib import suppress

import redis.asyncio as aioredis

from app.core.config import settings
from app.ws.events import USER_CHANNEL_PATTERN, parse_user_id
from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


async def redis_listener(manager: ConnectionManager) -> None:
    backoff = 1
    while True:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.psubscribe(USER_CHANNEL_PATTERN)
            logger.info("Redis listener subscribed to %s", USER_CHANNEL_PATTERN)
            backoff = 1
            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue
                try:
                    user_id = parse_user_id(message["channel"])
                except (IndexError, ValueError):
                    continue
                await manager.send_to_user(user_id, message["data"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis listener failed, reconnecting in %ss", backoff)
        finally:
            with suppress(Exception):
                await pubsub.aclose()
                await client.aclose()

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30)