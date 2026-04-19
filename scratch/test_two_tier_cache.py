import asyncio
import time
from src.core.cache import LLMCache
from src.core.redis_client import get_redis
from src.core.db import init_db

async def verify_two_tier():
    print("\n--- Initializing ---")
    init_db()
    
    prompt = "Two-tier cache test message 1"
    provider = "test_provider"
    model = "test_model"
    response = "This is a cached response from two-tier system."

    # 1. Clear existing cache for this prompt
    from src.core.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM llm_cache WHERE prompt_hash = %s", (LLMCache._generate_hash(prompt, provider, model),))
    
    redis = await get_redis()
    if redis:
        await redis.delete(f"llm_cache:{LLMCache._generate_hash(prompt, provider, model)}")
        print("Redis L1 cleared.")

    # 2. Store in two-tier
    print("\n--- Storing in Cache (L1 + L2) ---")
    await LLMCache.set(prompt, provider, model, response)

    # 3. Test L1 Hit
    print("\n--- Testing L1 (Redis) ---")
    start = time.perf_counter()
    hit1 = await LLMCache.get(prompt, provider, model)
    dur1 = time.perf_counter() - start
    print(f"L1 Hit: {hit1 is not None}, Duration: {dur1:.6f}s")
    
    # 4. Simulate Redis failure/clearing to test L2 fallback
    if redis:
        print("\n--- Clearing L1 to test L2 Fallback ---")
        await redis.delete(f"llm_cache:{LLMCache._generate_hash(prompt, provider, model)}")
        
        start = time.perf_counter()
        hit2 = await LLMCache.get(prompt, provider, model)
        dur2 = time.perf_counter() - start
        print(f"L2 Fallback Hit: {hit2 is not None}, Duration: {dur2:.6f}s")
        
        # 5. Verify L1 was re-populated
        start = time.perf_counter()
        hit3 = await LLMCache.get(prompt, provider, model)
        dur3 = time.perf_counter() - start
        print(f"L1 Re-hit (from L2 populate): {hit3 is not None}, Duration: {dur3:.6f}s")
        assert dur3 < dur2, "Re-hit should be faster than fallback"
    else:
        print("\n⚠️ Redis not running - Testing L2 only.")
        start = time.perf_counter()
        hit_only_l2 = await LLMCache.get(prompt, provider, model)
        print(f"L2 Only Hit: {hit_only_l2 is not None}, Duration: {time.perf_counter() - start:.6f}s")

    print("\n✅ Two-tier verification complete!")

if __name__ == "__main__":
    asyncio.run(verify_two_tier())
