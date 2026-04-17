import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger(name: str = "OpenClawBot") -> logging.Logger:
    """Configures and returns a centralized logger."""
    logger = logging.getLogger(name)

    # If the logger already has handlers, don't add more (avoids duplicate logs)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Define formats
        file_formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')
        console_formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')

        # Ensure the data directory exists
        os.makedirs("data", exist_ok=True)
        log_file_path = os.path.join("data", "bot.log")

        # File Handler (Rotating, max 5MB, keep 3 backups)
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)

        # Attach handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
