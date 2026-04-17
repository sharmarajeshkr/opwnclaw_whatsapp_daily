import os
from dotenv import load_dotenv

_env_loaded = False

def load_env():
    global _env_loaded
    if not _env_loaded:
        load_dotenv()
        _env_loaded = True

def get_openai_key() -> str | None:
    load_env()
    return os.getenv("OPENAI_API_KEY")

def get_gemini_key() -> str | None:
    load_env()
    return os.getenv("GEMINI_API_KEY")

def require_llm_key() -> str:
    openai_key = get_openai_key()
    gemini_key = get_gemini_key()
    if openai_key:
        return openai_key
    if gemini_key:
        return gemini_key
    raise ValueError("Neither OPENAI_API_KEY nor GEMINI_API_KEY is set in the environment.")

def get_whatsapp_target_number() -> str | None:
    load_env()
    return os.getenv("WHATSAPP_TARGET_NUMBER")

def get_whatsapp_session_name() -> str:
    load_env()
    return os.getenv("WHATSAPP_SESSION_NAME", "interview_bot")

def get_schedule_time() -> str:
    load_env()
    return os.getenv("SCHEDULE_TIME", "06:00")

def get_interview_topic() -> str:
    load_env()
    return os.getenv("INTERVIEW_TOPIC", "Software Engineering")
