import os
from app.core.config import settings
from app.core.logging import get_logger, log_duration
from app.core.limiter import TokenBucketLimiter
from app.services.cache_service import LLMCache

logger = get_logger("LLMProvider")

# Global LLM Limiter: 20 RPM (0.33 tokens/sec) with burst capacity of 5
llm_limiter = TokenBucketLimiter(rate=0.33, capacity=5)

class LLMProvider:
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.gemini_key = settings.GEMINI_API_KEY
        
        if self.openai_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.openai_key)
            self.model_name = "gpt-4o-mini"
            self.provider = "openai"
        elif self.gemini_key:
            from google import genai
            self.gemini_client = genai.Client(api_key=self.gemini_key)
            self.model_name = 'gemini-2.5-flash'
            self.provider = "gemini"
        else:
            raise ValueError("No API key found for Gemini or OpenAI in environment.")

    @log_duration(logger)
    async def generate_response(self, prompt: str) -> str:
        import asyncio
        
        # 1. Check Cache
        cached = await LLMCache.get(prompt, self.provider, self.model_name)
        if cached:
            return cached

        # 2. Rate Limit
        await llm_limiter.consume(wait=True)
        logger.debug(f"Generating response with {self.provider}...")
        try:
            if self.provider == "gemini":
                # Google GenAI generation is synchronous, blocking the event loop
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model=self.model_name,
                    contents=prompt
                )
                text = response.text
            elif self.provider == "openai":
                # OpenAI generation is synchronous here (using OpenAI instead of AsyncOpenAI)
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.choices[0].message.content
            
            # 3. Store in Cache
            if text:
                await LLMCache.set(prompt, self.provider, self.model_name, text)
            return text

        except Exception as e:
            logger.error(f"Error generating response from {self.provider}: {e}")
            raise
        return ""

    @log_duration(logger)
    async def generate_image(self, prompt: str) -> str:
        await llm_limiter.consume(wait=True)
        """
        Generates an image via OpenAI DALL-E and returns the local file path.
        Currently implemented as a safe stub to avoid unintentional costs.
        """
        logger.warning("Image generation (DALL-E) is currently disabled as a safe stub.")
        # If implementation is desired later:
        # if self.provider == "openai":
        #     response = self.client.images.generate(model="dall-e-3", prompt=prompt, size="1024x1024", n=1)
        #     image_url = response.data[0].url
        #     ... save url to local path ...
        return ""
