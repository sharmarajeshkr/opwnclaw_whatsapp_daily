import json
import os
import glob
from typing import Dict, Any, List

USERS_DIR = os.path.join("data", "users")

DEFAULT_CONFIG = {
    "schedule_time": "20:00",
    "topics": {
        "topic_1": "Architecture Challenge",
        "topic_2": "Kafka",
        "topic_3": "Agentic AI",
        "topic_4": "AI News",
        "topic_5": "Latest Global News"
    },
    "channels": {
        "whatsapp_target": "", # Dynamic per user
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "slack_webhook_url": ""
    }
}

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
    def load_config(phone_number: str) -> Dict[str, Any]:
        """Loads configuration for a specific user. Creates it with defaults if it doesn't exist."""
        path = ConfigManager.get_config_path(phone_number)
        if not os.path.exists(path):
            default_for_user = DEFAULT_CONFIG.copy()
            default_for_user["channels"]["whatsapp_target"] = phone_number
            ConfigManager.save_config(phone_number, default_for_user)
            return default_for_user
        
        try:
            with open(path, "r") as f:
                config = json.load(f)
                
            # Merge with defaults in case of missing keys
            merged = DEFAULT_CONFIG.copy()
            for k, v in config.items():
                if isinstance(v, dict) and k in merged:
                    merged[k].update(v)
                else:
                    merged[k] = v
            return merged
        except Exception as e:
            print(f"Error loading config for {phone_number}: {e}. Returning defaults.")
            default_for_user = DEFAULT_CONFIG.copy()
            default_for_user["channels"]["whatsapp_target"] = phone_number
            return default_for_user

    @staticmethod
    def save_config(phone_number: str, config: Dict[str, Any]):
        """Saves configuration for a specific user to data/users/<num>_config.json."""
        path = ConfigManager.get_config_path(phone_number)
        with open(path, "w") as f:
            json.dump(config, f, indent=4)

    @staticmethod
    def get_all_users() -> List[str]:
        """Returns a list of phone numbers of all registered users."""
        ConfigManager._ensure_users_dir()
        files = glob.glob(os.path.join(USERS_DIR, "*_config.json"))
        return [os.path.basename(f).replace("_config.json", "") for f in files]
