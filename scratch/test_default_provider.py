import asyncio
from app.llm.provider import LLMProvider

async def main():
    provider = LLMProvider()
    print(f"Default provider: {provider.provider}")
    print(f"Default model:    {provider.model_name}")
    print()

    # Test 1: No override — should use default OpenAI/Gemini exactly as before
    print("--- Test 1: Default (no override_model) ---")
    try:
        resp = await provider.generate_response("Say 'Hello from OpenAI!' and nothing else.")
        print(f"✅ Response: {resp}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 2: Explicit OpenAI override to confirm it still works
    print("\n--- Test 2: Explicit openai/gpt-4o-mini override ---")
    try:
        resp2 = await provider.generate_response("What is 3+3? One word only.", override_model="openai/gpt-4o-mini")
        print(f"✅ Response: {resp2}")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == '__main__':
    asyncio.run(main())
