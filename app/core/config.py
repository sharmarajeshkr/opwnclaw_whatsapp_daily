import os
import json
import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet
from app.core.logging import get_logger

logger = get_logger("ConfigManager")

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

    # Redis Settings
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    def get_database_url(self) -> str:
        """Returns the PostgreSQL DSN connection string."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = SystemConfig()

# ── User Configuration Models ──────────────────────────────────────────────────

class TopicsConfig(BaseModel):
    topic_1: str = "Architecture Challenge"
    topic_1_time: str = ""   # custom time e.g. "08:30" — empty = use global schedule_time
    topic_2: str = "Kafka"
    topic_2_time: str = ""
    topic_3: str = "Agentic AI"
    topic_3_time: str = ""
    topic_4: str = "AI News"
    topic_4_time: str = ""
    topic_5: str = "Latest Global News"
    topic_5_time: str = ""

class ChannelsConfig(BaseModel):
    whatsapp_target: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    slack_webhook_url: str = ""

class UserConfig(BaseModel):
    schedule_time: str = "20:00"   # global fallback if a topic has no individual time
    timezone: str = "Asia/Kolkata"
    pin_code: str = "0000"
    topics: TopicsConfig = Field(default_factory=TopicsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    level: str = "Beginner"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    skill_profile: Dict[str, int] = Field(default_factory=lambda: {"backend": 5, "system_design": 5, "ai": 5})

# ── Config Manager ─────────────────────────────────────────────────────────────

class ConfigManager:
    @staticmethod
    def _get_fernet() -> Fernet | None:
        key = settings.FERNET_KEY
        if not key:
            return None
        return Fernet(key.encode("utf-8"))

    @staticmethod
    def _encrypt_dict(data: dict) -> dict:
        fernet = ConfigManager._get_fernet()
        if not fernet:
            return data
        
        channels = data.get("channels", {})
        if "telegram_bot_token" in channels and channels["telegram_bot_token"]:
            channels["telegram_bot_token"] = fernet.encrypt(channels["telegram_bot_token"].encode("utf-8")).decode("utf-8")
        if "slack_webhook_url" in channels and channels["slack_webhook_url"]:
            channels["slack_webhook_url"] = fernet.encrypt(channels["slack_webhook_url"].encode("utf-8")).decode("utf-8")
        return data

    @staticmethod
    def _decrypt_dict(data: dict) -> dict:
        fernet = ConfigManager._get_fernet()
        if not fernet:
            return data
            
        channels = data.get("channels", {})
        for key in ["telegram_bot_token", "slack_webhook_url"]:
            if key in channels and channels[key]:
                try:
                    if channels[key].startswith("gAAAAA"):
                        channels[key] = fernet.decrypt(channels[key].encode("utf-8")).decode("utf-8")
                except Exception:
                    pass
        return data

    @staticmethod
    def load_config(phone_number: str) -> UserConfig:
        """Loads configuration for a specific user from PostgreSQL. Creates it with defaults if not found."""
        from app.database.db import get_conn
        
        try:
            with get_conn() as conn:
                row = conn.execute("SELECT * FROM user_configs WHERE phone_number = %s", (phone_number,)).fetchone()
                
            if not row:
                config = UserConfig()
                config.channels.whatsapp_target = phone_number
                ConfigManager.save_config(phone_number, config)
                return config
            
            data = {
                "schedule_time": row["schedule_time"],
                "timezone": row["timezone"],
                "pin_code": row["pin_code"],
                "topics": row["topics"],
                "channels": row["channels"],
                "level": row.get("level", "Beginner"),
                "created_at": row.get("created_at", datetime.datetime.now()),
                "skill_profile": row.get("skill_profile", {"backend": 5, "system_design": 5, "ai": 5}),
            }
            data = ConfigManager._decrypt_dict(data)
            return UserConfig.model_validate(data)
            
        except Exception as e:
            logger.error(f"Error loading config for {phone_number}: {e}. Returning defaults.")
            config = UserConfig()
            config.channels.whatsapp_target = phone_number
            return config

    @staticmethod
    def save_config(phone_number: str, config: UserConfig | Dict[str, Any]):
        """Upserts configuration for a specific user into PostgreSQL."""
        from app.database.db import get_conn
        
        if isinstance(config, UserConfig):
            data = config.model_dump()
        else:
            data = config
            
        data = ConfigManager._encrypt_dict(data)
        
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_configs (phone_number, schedule_time, timezone, pin_code, topics, channels, level, skill_profile, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (phone_number) DO UPDATE SET
                    schedule_time = EXCLUDED.schedule_time,
                    timezone      = EXCLUDED.timezone,
                    pin_code      = EXCLUDED.pin_code,
                    topics        = EXCLUDED.topics,
                    channels      = EXCLUDED.channels,
                    level         = EXCLUDED.level,
                    skill_profile = EXCLUDED.skill_profile,
                    updated_at    = CURRENT_TIMESTAMP
                """,
                (
                    phone_number,
                    data.get("schedule_time"),
                    data.get("timezone"),
                    data.get("pin_code"),
                    json.dumps(data.get("topics", {})),
                    json.dumps(data.get("channels", {})),
                    data.get("level", "Beginner"),
                    json.dumps(data.get("skill_profile", {})),
                )
            )

    @staticmethod
    def get_all_users() -> List[str]:
        """Returns a list of phone numbers of all ACTIVE registered users from PostgreSQL."""
        from app.database.db import get_conn
        with get_conn() as conn:
            # Only return users who are marked as active in user_status
            rows = conn.execute(
                "SELECT phone_number FROM user_status WHERE is_active = TRUE"
            ).fetchall()
        return [row["phone_number"] for row in rows]
