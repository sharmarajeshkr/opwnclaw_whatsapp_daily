import asyncio
import time
from src.content.llm import LLMProvider
from src.core.db import init_db

async def test_caching():
    print("\n--- Initializing DB ---")
    init_db()
    
    llm = LLMProvider()
    test_prompt = "Say 'Hello Cache World' once."
    
    print("\n--- Call 1 (API Hit) ---")
    start1 = time.perf_counter()
    resp1 = await llm.generate_response(test_prompt)
    dur1 = time.perf_counter() - start1
    print(f"Response: {resp1}")
    print(f"Duration: {dur1:.4f}s")
    
    print("\n--- Call 2 (Cache Hit) ---")
    start2 = time.perf_counter()
    resp2 = await llm.generate_response(test_prompt)
    dur2 = time.perf_counter() - start2
    print(f"Response: {resp2}")
    print(f"Duration: {dur2:.4f}s")
    
    # Verification
    assert resp1 == resp2, "Responses must be identical"
    # Even with local network, API call takes >0.5s. Cache takes <0.05s.
    if dur2 < 0.1:
        print("\n✅ CACHE VERIFIED: Second call was near-instant.")
    else:
        print("\n❌ CACHE FAILED: Second call took too long.")
        
    assert dur2 < dur1, "Second call must be faster than the first"

if __name__ == "__main__":
    asyncio.run(test_caching())
