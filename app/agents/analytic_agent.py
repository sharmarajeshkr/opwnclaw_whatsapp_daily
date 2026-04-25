"""
app/agents/analytic_agent.py
----------------------------
Specialized agent for generating long-term technical growth insights and 
summarizing weekly performance patterns.
"""
import json
from app.llm.provider import LLMProvider
from app.core.logging import get_logger
from app.mcp.client import run_mcp_tool

logger = get_logger("AnalyticAgent")

class AnalyticAgent:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.llm = LLMProvider()

    async def generate_weekly_insight(self, weekly_data: list[dict], level: str) -> str:
        """
        Generates a personalized "Weekly AI Insight" based on technical performance.
        Now integrates real-world search to provide valid roadmap resources.
        
        Args:
            weekly_data: List of dicts containing {topic, score, weak_aspects, feedback, question_text}
            level: User's current technical level (e.g., 'Intermediate')
        """
        if not weekly_data:
            return "No performance data recorded this week. Keep practicing to unlock AI insights!"

        # 1. Prepare context and identify weak areas for search
        formatted_data = []
        weak_topics = set()
        for entry in weekly_data:
            formatted_data.append({
                "topic": entry["topic"],
                "score": entry["score"],
                "question": entry["question_text"],
                "feedback": entry["feedback"],
                "weak_points": entry["weak_aspects"]
            })
            if entry["score"] < 7:
                weak_topics.add(entry["topic"])

        # 2. Fetch real-world resources for the roadmap
        resource_context = ""
        if weak_topics:
            search_query = " ".join(list(weak_topics)[:2]) # Limit to top 2 themes
            try:
                logger.info(f"[*] AnalyticAgent: Fetching real-world resources for: {search_query}")
                search_results = await run_mcp_tool("get_tech_news", {"query": search_query, "limit": 3})
                resource_context = f"\nREAL-WORLD RESOURCES FOR ROADMAP:\n{search_results}\n"
            except Exception as e:
                logger.error(f"Search failed in AnalyticAgent: {e}")

        # 3. Final Prompt
        prompt = (
            f"You are a Principal AI Mentor. Analyze the following technical performance data for a {level} level student "
            f"from the past 7 days and generate a high-level 'Weekly AI Insight'.\n\n"
            f"WEEKLY DATA (JSON):\n{json.dumps(formatted_data, indent=2)}\n\n"
            f"{resource_context}\n"
            "YOUR TASK:\n"
            "1. Identify meta-patterns: Look across different topics for recurring conceptual blockers (e.g. 'You tend to neglect concurrency safety').\n"
            "2. Reference specific struggles: Mention 1-2 exact questions where the student scored low.\n"
            "3. Provide a 'Mentor's Roadmap': 2-3 specific technical goals for next week. "
            "IMPORTANT: If real resources are provided above, include them in the roadmap with their EXACT links. "
            "If no resources are provided, DO NOT hallucinate links; instead, recommend specific official documentation (e.g. docs.python.org).\n\n"
            "CRITICAL: Never hallucinate URLs. Never use example.com.\n\n"
            "FORMATTING:\n"
            "- Use WhatsApp markdown (*bold*, _italic_).\n"
            "- Use '💡 *Weekly AI Insight*' as the header.\n"
            "- Keep the tone professional, encouraging, and deeply technical.\n"
            "- Total length: Max 350-400 words.\n"
        )
        
        try:
            response = await self.llm.generate_response(prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating weekly insight: {e}")
            return "Unable to generate your weekly insight at this time. Our AI mentors are resting!"
