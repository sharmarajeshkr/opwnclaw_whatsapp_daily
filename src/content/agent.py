import os
from src.content.llm import LLMProvider
from src.content.history import UserHistoryManager
from src.core.logger import get_logger

logger = get_logger("InterviewAgent")

class InterviewAgent:
    def __init__(self, phone_number: str, topic: str = "Software Engineering"):
        self.llm = LLMProvider()
        self.history_manager = UserHistoryManager(phone_number)
        self.topic = topic

    async def get_daily_challenge(self) -> tuple[str, str]:
        """Returns (detailed_text, image_prompt) for the daily challenge, avoiding history."""
        history = self.history_manager.get_history("challenges")
        history_str = "\n".join([f"- {h}" for h in history])
        
        prompt = f"""
        Generate a high-quality HLD/LLD Architecture Challenge and a DEEP-DIVE Solution for a Senior Architect role.
        
        Topics: Kafka, Spring Boot, microservices, Distributed Tracing, Circuit Breaker, API Gateway, caching, DB scaling, Python, ML, Agentic AI.
        
        PREVIOUS CHALLENGES TO AVOID:
        {history_str}
        
        Style Example: "Design a payment retry platform handling 10M events/day."
        
        The Solution MUST be extremely detailed and cover:
        1. *High-Level Design (HLD)* - Component interaction, data flow, throughput scaling.
        2. *Database Schema* - Exact tables, indexing strategies, data types (JSONB, partitions).
        3. *Event/Logic Flow* - Microservice coordination, Kafka topics, state transitions.
        4. *Reliability* - Retry + DLQ, Circuit Breakers, idempotency keys, fallout management.
        5. *Observability* - Distributed tracing (OpenTelemetry), key metrics, SLOs.
        
        Provide:
        - *Architectural Challenge* (The Problem).
        - *Proposed Solution* (Deep-dive sections 1-5).        
        
        Format the output for WhatsApp (use *bold* for headers and list items).
        """
        response = await self.llm.generate_response(prompt)
        
        # Add a snippet of the challenge to history
        first_line = response.split('\n', 1)[0].strip('*')[:200]
        self.history_manager.add_to_history("challenges", first_line)

        return response.strip(), "A professional technical architecture diagram of a high-scale distributed system."

    async def get_deep_dive(self, subject: str) -> str:
        """Returns a deep-dive technical question and answer for a specific subject."""
        history = self.history_manager.get_history(subject)
        history_str = "\n".join([f"- {h}" for h in history])
        
        prompt = f"""
        Generate a senior-level technical deep-dive Question and Answer focused entirely on '{subject}'.
        
        PREVIOUS TOPICS COVERED (DO NOT REPEAT):
        {history_str}
        
        Provide:
        - *The Question*: A complex, real-world scenario or conceptual deep-dive related to {subject}.
        - *The Detailed Answer*: A 500-800 word explanation covering mechanics, trade-offs, and best practices.
        
        Format for WhatsApp (use *bold* for headers and list items).
        """
        response = await self.llm.generate_response(prompt)
        
        # Add the first line to history to avoid repetition
        first_line = response.split('\n', 1)[0].strip('*')[:200]
        self.history_manager.add_to_history(subject, first_line)
        return response.strip()

    async def get_curated_content(self, category: str, raw_search_results: str) -> str:
        """Summarizes search results for a specific category while avoiding history."""
        history = self.history_manager.get_history(category)
        history_str = "\n".join([f"- {h}" for h in history])
        
        prompt = f"""
        Given the following raw research on '{category}', summarize it for a WhatsApp update.
        
        PREVIOUS {category.upper()} SENT (DO NOT REPEAT):
        {history_str}
        
        Provide:
        - 3-4 top entries, each with:
            - A concise *Title*.
            - A 500-1000 word *Summary*.
            - A *Read More* link (google search link for the topic).
        - Format for WhatsApp (use *bold* for headers and > for descriptions).
        - Be concise but informative.
        
        RESEARCH:
        {raw_search_results}
        """
        summary = await self.llm.generate_response(prompt)
        # Add some identifiers to history
        self.history_manager.add_to_history(category, summary[:500])
        return summary.strip()
