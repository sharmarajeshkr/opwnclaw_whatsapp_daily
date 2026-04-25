import hashlib
from app.core.redis_client import get_redis
from app.core.logging import get_logger

logger = get_logger("LLMCache")

class LLMCache:
    """
    Single-tier in-memory caching for LLM responses via Redis.
    If Redis is unavailable the cache is silently skipped — no DB dependency.
    """

    # Time-To-Live for Redis entries in seconds (24 hours)
    REDIS_TTL = 86400

    @staticmethod
    def _generate_hash(prompt: str, provider: str, model: str) -> str:
        """Creates a unique deterministic hash for the request context."""
        payload = f"{provider}:{model}:{prompt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    async def get(cls, prompt: str, provider: str, model: str) -> str | None:
        """Retrieves a cached response from Redis. Returns None on miss or unavailability."""
        p_hash = cls._generate_hash(prompt, provider, model)
        redis = await get_redis()
        if redis:
            try:
                cached = await redis.get(f"llm_cache:{p_hash}")
                if cached:
                    logger.debug(f"🚀 Cache Hit (Redis) for hash={p_hash[:10]}...")
                    return cached
            except Exception as e:
                logger.warning(f"Redis Cache get error: {e}")
        return None

    @classmethod
    async def set(cls, prompt: str, provider: str, model: str, response: str):
        """Stores a response in Redis. Silently skips if Redis is unavailable."""
        p_hash = cls._generate_hash(prompt, provider, model)
        redis = await get_redis()
        if redis:
            try:
                await redis.setex(f"llm_cache:{p_hash}", cls.REDIS_TTL, response)
                logger.debug(f"Cached response to Redis with TTL={cls.REDIS_TTL}s")
            except Exception as e:
                logger.warning(f"Redis Cache set error: {e}")
