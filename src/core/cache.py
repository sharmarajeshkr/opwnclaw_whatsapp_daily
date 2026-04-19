import hashlib
import asyncio
from src.core.db import get_conn
from src.core.redis_client import get_redis
from src.core.logger import get_logger

logger = get_logger("LLMCache")

class LLMCache:
    """
    Two-tier persistent caching for LLM responses.
    L1: Redis (In-memory, fast, TTL-based)
    L2: PostgreSQL (Persistent, durable)
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
        """Retrieves a cached response using L1 (Redis) -> L2 (PostgreSQL)."""
        p_hash = cls._generate_hash(prompt, provider, model)
        redis_key = f"llm_cache:{p_hash}"

        # 1. Try L1: Redis
        redis = await get_redis()
        if redis:
            try:
                cached = await redis.get(redis_key)
                if cached:
                    logger.debug(f"🚀 L1 Cache Hit (Redis) for hash={p_hash[:10]}...")
                    return cached
            except Exception as e:
                logger.warning(f"L1 Cache Error: {e}")

        # 2. Try L2: PostgreSQL
        with get_conn() as conn:
            row = conn.execute(
                "SELECT response_text FROM llm_cache WHERE prompt_hash = %s",
                (p_hash,)
            ).fetchone()
            if row:
                response = row["response_text"]
                logger.debug(f"💾 L2 Cache Hit (PostgreSQL) for hash={p_hash[:10]}...")
                
                # Populating L1 for next time
                if redis:
                    try:
                        await redis.setex(redis_key, cls.REDIS_TTL, response)
                    except Exception:
                        pass
                return response

        return None

    @classmethod
    async def set(cls, prompt: str, provider: str, model: str, response: str):
        """Stores a new response in both L1 (Redis) and L2 (PostgreSQL)."""
        p_hash = cls._generate_hash(prompt, provider, model)
        redis_key = f"llm_cache:{p_hash}"

        # 1. Store in L2: PostgreSQL (Durable)
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO llm_cache (prompt_hash, provider, model, prompt_text, response_text) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (prompt_hash) DO NOTHING",
                    (p_hash, provider, model, prompt, response)
                )
                logger.debug(f"Persisted new response to L2 Cache (PostgreSQL)")
        except Exception as e:
            logger.warning(f"L2 Save Error: {e}")

        # 2. Store in L1: Redis (Fast)
        redis = await get_redis()
        if redis:
            try:
                await redis.setex(redis_key, cls.REDIS_TTL, response)
                logger.debug(f"Cached new response to L1 Cache (Redis) with TTL={cls.REDIS_TTL}s")
            except Exception as e:
                logger.warning(f"L1 Save Error: {e}")
