import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class SystemConfig(BaseSettings):
    # LLM Settings
    OPENAI_API_KEY: str | None = Field(default=None)
    GEMINI_API_KEY: str | None = Field(default=None)
    
    # Bot Settings
    INTERVIEW_TOPIC: str = Field(default="Software Engineering")
    SCHEDULE_TIME: str = Field(default="06:00")
    WHATSAPP_SESSION_NAME: str = Field(default="interview_bot")
    WHATSAPP_TARGET_NUMBER: str | None = Field(default=None)
    
    # Security / Admin Settings
    ADMIN_PASSWORD: str | None = Field(default=None)
    API_SECRET_KEY: str | None = Field(default=None)
    FERNET_KEY: str | None = Field(default=None)
    
    # PostgreSQL Database Settings
    POSTGRES_SERVER: str = Field(default="localhost")
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres") 
    POSTGRES_PORT: str = Field(default="5432")
    POSTGRES_DB: str = Field(default="openclaw")

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    def get_database_url(self) -> str:
        """Returns the PostgreSQL DSN connection string."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = SystemConfig()
