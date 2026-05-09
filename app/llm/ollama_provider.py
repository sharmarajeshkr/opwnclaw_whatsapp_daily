"""
app/llm/ollama_provider.py
--------------------------
NEW FILE — Ollama-specific LLM provider.
Drop-in replacement for LLMProvider but routes ALL calls through a
local Ollama instance via its OpenAI-compatible REST API.

Usage:
    from app.llm.ollama_provider import OllamaProvider
    llm = OllamaProvider(model="llama3.1:8b")
    result = await llm.generate_response("Your prompt here")

The original app/llm/provider.py is NOT modified.
"""
import os
import asyncio
from app.core.logging import get_logger, log_duration
from app.core.limiter import TokenBucketLimiter
from app.services.cache_service import LLMCache

logger = get_logger("OllamaProvider")

# Shared rate limiter — same bucket as LLMProvider to honour global RPM
ollama_limiter = TokenBucketLimiter(rate=0.33, capacity=5)

# Default Ollama API endpoint (OpenAI-compatible)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")


class OllamaProvider:
    """
    A self-contained LLM provider that talks exclusively to a local Ollama server.
    Implements the same async interface as LLMProvider so agents can use it
    interchangeably without any changes to the original agent files.
    """

    provider = "ollama"

    def __init__(self, model: str):
        """
        Args:
            model: The Ollama model name to use, e.g. "llama3.1:8b", "phi3:mini".
                   Run `ollama list` to see what is available locally.
        """
        self.model_name = model
        try:
            from openai import OpenAI
            self.client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
            logger.info(f"OllamaProvider initialised: model={model}, url={OLLAMA_BASE_URL}")
        except ImportError:
            raise RuntimeError(
                "The 'openai' package is required to use OllamaProvider. "
                "Install it with: pip install openai"
            )

    @log_duration(logger)
    async def generate_response(self, prompt: str) -> str:
        """
        Send a prompt to the local Ollama model and return the text response.
        Caching and rate-limiting are applied the same way as LLMProvider.
        """
        # 1. Check Cache
        cached = await LLMCache.get(prompt, self.provider, self.model_name)
        if cached:
            logger.debug(f"Cache hit for ollama/{self.model_name}")
            return cached

        # 2. Rate Limit
        await ollama_limiter.consume(wait=True)
        logger.debug(f"Sending prompt to ollama/{self.model_name}...")

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content

            # 3. Store in Cache
            if text:
                await LLMCache.set(prompt, self.provider, self.model_name, text)
            return text

        except Exception as e:
            logger.error(f"OllamaProvider error (model={self.model_name}): {e}")
            raise

    async def generate_image(self, prompt: str) -> str:
        """Stub — Ollama does not support image generation."""
        logger.warning("OllamaProvider: generate_image() is not supported. Returning empty string.")
        return ""
