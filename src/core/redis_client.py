import redis.asyncio as redis
from src.core.sys_config import settings
from src.core.logger import get_logger

logger = get_logger("RedisClient")

class RedisManager:
    """
    Manages the asynchronous Redis connection pool.
    """
    _client = None
    _failed = False

    @classmethod
    async def get_client(cls):
        if cls._failed:
            return None

        if cls._client is None:
            try:
                cls._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                await cls._client.ping()
                logger.info(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e}. Falling back to PostgreSQL only.")
                cls._client = None
                cls._failed = True
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None

# Global helper for quick access
async def get_redis():
    return await RedisManager.get_client()
