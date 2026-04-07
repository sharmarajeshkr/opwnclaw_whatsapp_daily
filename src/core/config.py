import json
import os
import glob
from typing import Dict, Any, List
from pydantic import BaseModel, Field

USERS_DIR = os.path.join("data", "users")

class TopicsConfig(BaseModel):
    topic_1: str = "Architecture Challenge"
    topic_2: str = "Kafka"
    topic_3: str = "Agentic AI"
    topic_4: str = "AI News"
    topic_5: str = "Latest Global News"

class ChannelsConfig(BaseModel):
    whatsapp_target: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    slack_webhook_url: str = ""

class UserConfig(BaseModel):
    schedule_time: str = "20:00"
    topics: TopicsConfig = Field(default_factory=TopicsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)

class ConfigManager:
    @staticmethod
    def _ensure_users_dir():
        if not os.path.exists(USERS_DIR):
            os.makedirs(USERS_DIR, exist_ok=True)

    @staticmethod
    def get_config_path(phone_number: str) -> str:
        ConfigManager._ensure_users_dir()
        return os.path.join(USERS_DIR, f"{phone_number}_config.json")

    @staticmethod
    def load_config(phone_number: str) -> UserConfig:
        """Loads configuration for a specific user. Creates it with defaults if it doesn't exist."""
        path = ConfigManager.get_config_path(phone_number)
        if not os.path.exists(path):
            config = UserConfig()
            config.channels.whatsapp_target = phone_number
            ConfigManager.save_config(phone_number, config)
            return config
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return UserConfig.model_validate(data)
        except Exception as e:
            from src.core.logger import get_logger
            logger = get_logger("ConfigManager")
            logger.error(f"Error loading config for {phone_number}: {e}. Returning defaults.")
            config = UserConfig()
            config.channels.whatsapp_target = phone_number
            return config

    @staticmethod
    def save_config(phone_number: str, config: UserConfig | Dict[str, Any]):
        """Saves configuration for a specific user to data/users/<num>_config.json."""
        path = ConfigManager.get_config_path(phone_number)
        if isinstance(config, UserConfig):
            data = config.model_dump()
        else:
            data = config
            
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def get_all_users() -> List[str]:
        """Returns a list of phone numbers of all registered users."""
        ConfigManager._ensure_users_dir()
        files = glob.glob(os.path.join(USERS_DIR, "*_config.json"))
        return [os.path.basename(f).replace("_config.json", "") for f in files]
