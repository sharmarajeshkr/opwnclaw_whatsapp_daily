import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.agents.analytic_agent import AnalyticAgent

async def main():
    print("Testing AnalyticAgent with real-world search...")
    agent = AnalyticAgent("919876543210")
    
    # Mock data with a clear weakness in Kafka
    weekly_data = [
        {
            "topic": "Kafka",
            "score": 4,
            "question_text": "How do you handle rebalance storms?",
            "feedback": "Poor understanding of static membership.",
            "weak_aspects": ["Static Membership", "Consumer Group Protocol"]
        }
    ]
    
    try:
        insight = await agent.generate_weekly_insight(weekly_data, "Intermediate")
        print("\n--- WEEKLY INSIGHT PREVIEW ---\n")
        print(insight)
        print("\n------------------------------\n")
        
        # Check if real links (search results) were injected
        if "http" in insight and "example.com" not in insight:
            print("SUCCESS: AnalyticAgent provided non-hallucinated links in the roadmap.")
        else:
            print("WARNING: No links found or placeholder found. verify prompt logic.")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
