import os
from src.core.env import get_openai_key, get_gemini_key
from src.core.logger import get_logger

logger = get_logger("LLMProvider")

class LLMProvider:
    def __init__(self):
        self.openai_key = get_openai_key()
        self.gemini_key = get_gemini_key()
        
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
            raise ValueError("No API key found for Gemini or OpenAI in environment.")

    async def generate_response(self, prompt: str) -> str:
        import asyncio
        logger.debug(f"Generating response with {self.provider}...")
        try:
            if self.provider == "gemini":
                # Google GenAI generation is synchronous, blocking the event loop
                response = await asyncio.to_thread(self.model.generate_content, prompt)
                return response.text
            elif self.provider == "openai":
                # OpenAI generation is synchronous here (using OpenAI instead of AsyncOpenAI)
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating response from {self.provider}: {e}")
            raise
        return ""

    async def generate_image(self, prompt: str) -> str:
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
