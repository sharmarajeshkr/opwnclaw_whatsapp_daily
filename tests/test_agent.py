import asyncio
import os
from src.agent import InterviewAgent
from dotenv import load_dotenv

async def test_generation():
    print("Testing Interview Question Generation...")
    load_dotenv()
    
    try:
        agent = InterviewAgent(topic=os.getenv("INTERVIEW_TOPIC", "Software Engineering"))
        question = await agent.get_daily_question()
        
        print("\n--- GENERATED QUESTION ---")
        print(question)
        print("--------------------------")
        print("\nSuccess! Your LLM configuration is working correctly.")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nMake sure your GEMINI_API_KEY or OPENAI_API_KEY is set correctly in .env")

if __name__ == "__main__":
    asyncio.run(test_generation())
