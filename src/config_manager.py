import json
import os
from typing import Dict, Any

CONFIG_FILE = "config.json"

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
        "whatsapp_target": "+919789824976",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "slack_webhook_url": ""
    }
}

class ConfigManager:
    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Loads configuration from config.json. Creates it with defaults if it doesn't exist."""
        if not os.path.exists(CONFIG_FILE):
            ConfigManager.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                
            # Merge with defaults in case of missing keys in an older config
            merged = DEFAULT_CONFIG.copy()
            for k, v in config.items():
                if isinstance(v, dict) and k in merged:
                    merged[k].update(v)
                else:
                    merged[k] = v
            return merged
        except Exception as e:
            print(f"Error loading config: {e}. Returning defaults.")
            return DEFAULT_CONFIG

    @staticmethod
    def save_config(config: Dict[str, Any]):
        """Saves configuration to config.json."""
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
