import asyncio
from app.llm.provider import LLMProvider
from app.core.logging import get_logger

logger = get_logger('TestOllama')

async def main():
    try:
        provider = LLMProvider()
        print("--- Testing phi3:mini ---")
        try:
            resp1 = await provider.generate_response("What is the capital of France? Answer in one word.", override_model="ollama/phi3:mini")
            print(f"Phi3:mini Response: {resp1}")
        except Exception as e:
            print(f"Error with phi3:mini: {e}")
            print("Trying phi3...")
            resp1 = await provider.generate_response("What is the capital of France? Answer in one word.", override_model="ollama/phi3")
            print(f"Phi3 Response: {resp1}")

        print("\n--- Testing llama3.1:8b ---")
        try:
            resp2 = await provider.generate_response("What is 2+2? Answer in one word.", override_model="ollama/llama3.1:8b")
            print(f"Llama3.1:8b Response: {resp2}")
        except Exception as e:
            print(f"Error with llama3.1:8b: {e}")
            print("Trying llama3.1...")
            resp2 = await provider.generate_response("What is 2+2? Answer in one word.", override_model="ollama/llama3.1")
            print(f"Llama3.1 Response: {resp2}")
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
