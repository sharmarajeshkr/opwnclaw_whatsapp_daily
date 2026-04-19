import asyncio
import time
from src.core.limiter import TokenBucketLimiter, MultiUserLimiter

async def test_token_bucket():
    print("\n--- Testing TokenBucketLimiter (Rate=5 tokens/sec, Capacity=2) ---")
    limiter = TokenBucketLimiter(rate=5, capacity=2)
    
    start = time.perf_counter()
    results = []
    
    # Try consuming 10 tokens in a burst with wait=False
    print("Initial burst (wait=False):")
    for i in range(10):
        success = await limiter.consume(wait=False)
        results.append(success)
        print(f"Request {i+1}: {'OK' if success else 'FAIL'}")
    
    assert results[0] == True
    assert results[1] == True
    assert results[2] == False # Capacity exceeded
    
    print("\nQueued requests (wait=True):")
    q_start = time.perf_counter()
    # Consume 3 tokens with wait=True. Each should take ~0.2s after the first.
    for i in range(3):
        await limiter.consume(wait=True)
        print(f"Queued Request {i+1} handled at {time.perf_counter() - q_start:.2f}s")
    
    q_end = time.perf_counter()
    assert (q_end - q_start) > 0.3 # At least 2 refill cycles

async def test_multi_user():
    print("\n--- Testing MultiUserLimiter (Rate=1 per sec, Capacity=1) ---")
    limiter = MultiUserLimiter(rate=1, capacity=1)
    
    print("User A:")
    print(f"A1: {await limiter.consume('user_a', wait=False)}")
    print(f"A2: {await limiter.consume('user_a', wait=False)}") # Should fail
    
    print("\nUser B (Should be independent):")
    print(f"B1: {await limiter.consume('user_b', wait=False)}")
    print(f"B2: {await limiter.consume('user_b', wait=False)}") # Should fail

async def main():
    await test_token_bucket()
    await test_multi_user()
    print("\n✅ All rate limit logic tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
