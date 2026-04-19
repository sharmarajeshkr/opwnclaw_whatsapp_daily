import logging
import os
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON objects."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add extra context if provided (e.g. phone)
        if hasattr(record, "phone") and record.phone:
            log_record["phone"] = record.phone
            
        return json.dumps(log_record)

def get_logger(name: str = "OpenClawBot") -> logging.Logger:
    """Configures and returns a centralized logger."""
    logger = logging.getLogger(name)

    # Use LOG_LEVEL from env, default to INFO for console, DEBUG for file
    env_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, env_level, logging.INFO)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)  # Capture everything, filter at handler level

        # Define formats
        json_formatter = JSONFormatter()
        console_formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')

        # Ensure the data directory exists
        os.makedirs("data", exist_ok=True)
        log_file_path = os.path.join("data", "bot.log")

        # File Handler (JSON, max 5MB, keep 3 backups)
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(json_formatter)

        # Console Handler (Standard text)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)

        # Attach handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
