import asyncio
import time
from typing import Dict, Tuple
from app.core.logging import get_logger

logger = get_logger("RateLimiter")

class TokenBucketLimiter:
    """
    Standard asynchronous Token Bucket rate limiter.
    
    Tokens are added at a fixed 'rate' (tokens per second) up to a maximum 'capacity'.
    Each consume() call takes 1 token. If no tokens are available, it waits until
    the next token is refilled.
    """
    def __init__(self, rate: float, capacity: float):
        self.rate = rate  # refill rate (tokens/sec)
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.perf_counter()
        self.lock = asyncio.Lock()

    async def _refill(self):
        now = time.perf_counter()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))
        self.last_refill = now

    async def consume(self, wait: bool = True) -> bool:
        """
        Consumes 1 token.
        If wait=True, it will sleep until a token is available.
        If wait=False, it returns False immediately if no tokens are available.
        """
        async with self.lock:
            await self._refill()
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            if not wait:
                return False
            
            # Wait for 1 token to refill
            wait_time = (1 - self.tokens) / self.rate
            logger.debug(f"⏳ Rate limit reached. Throttling for {wait_time:.3f}s...")
            await asyncio.sleep(wait_time)
            
            # Re-refill after sleeping
            await self._refill()
            self.tokens -= 1
            return True

class MultiUserLimiter:
    """
    Manages a collection of limiters keyed by phone number/user ID.
    Used for per-user anti-spam protection.
    """
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.limiters: Dict[str, TokenBucketLimiter] = {}

    def get_limiter(self, user_id: str) -> TokenBucketLimiter:
        if user_id not in self.limiters:
            self.limiters[user_id] = TokenBucketLimiter(self.rate, self.capacity)
        return self.limiters[user_id]

    async def consume(self, user_id: str, wait: bool = False) -> bool:
        limiter = self.get_limiter(user_id)
        return await limiter.consume(wait=wait)
