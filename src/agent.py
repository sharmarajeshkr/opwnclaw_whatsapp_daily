import os
from dotenv import load_dotenv
from src.history_manager import HistoryManager
from src.logger_config import get_logger
logger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")


load_dotenv()

class LLMProvider:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if self.openai_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.openai_key)
            self.model_name = "gpt-4o-mini"
            self.provider = "openai"
        elif self.gemini_key:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self.provider = "gemini"
        else:
            raise ValueError("No API key found for Gemini or OpenAI in .env")

    async def generate_response(self, prompt: str) -> str:
        logger.debug(f"DEBUG: Generating response with {self.provider}...")
        if self.provider == "gemini":
            response = self.model.generate_content(prompt)
            logger.debug("DEBUG: Gemini response received.")
            return response.text
        elif self.provider == "openai":
            logger.debug(f"DEBUG: OpenAI ({self.model_name}) request starting...")
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            logger.debug("DEBUG: OpenAI response received.")
            return response.choices[0].message.content
        return ""

    async def generate_image(self, prompt: str) -> str:
        """Generates an image and returns the local file path."""
        if self.provider != "openai":
            logger.debug("DEBUG: Image generation currently only supported via OpenAI provider.")
            return ""

        import httpx        

class InterviewAgent:
    def __init__(self, topic: str = "Software Engineering"):
        self.llm = LLMProvider()
        self.topic = topic

    async def get_daily_challenge(self) -> tuple[str, str]:
        """Returns (detailed_text, image_prompt) for the daily challenge, avoiding history."""
        history = HistoryManager.get_history("challenges")
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
        return response.strip(), "A professional technical architecture diagram of a high-scale distributed system."

    async def get_deep_dive(self, subject: str) -> str:
        """Returns a deep-dive technical question and answer for a specific subject."""
        history = HistoryManager.get_history(subject)
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
        
        first_line = response.split('\n')[0].strip('*')[:100]
        HistoryManager.add_to_history(subject, first_line)
        return response.strip()

    async def get_curated_content(self, category: str, raw_search_results: str) -> str:
        """Summarizes search results for a specific category while avoiding history."""
        history = HistoryManager.get_history(category)
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
        # Add titles to history (this logic is simplified, usually we'd parse the summary)
        # For now, let's just record the first line
        HistoryManager.add_to_history(category, summary[:1000])
        return summary.strip()
