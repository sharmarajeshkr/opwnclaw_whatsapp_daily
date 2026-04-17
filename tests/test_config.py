import os
import json
import pytest
from cryptography.fernet import Fernet
from src.core.config import ConfigManager, UserConfig

def test_fernet_encryption_works(monkeypatch, tmp_path):
    # Setup isolated environment
    users_dir = tmp_path / "data" / "users"
    monkeypatch.setattr("src.core.config.USERS_DIR", str(users_dir))
    
    # Generate a dummy key
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr("src.core.config.get_fernet_key", lambda: key)

    phone = "919999999999"
    cfg = UserConfig()
    cfg.channels.telegram_bot_token = "TELEGRAM_SECRET_123"
    cfg.channels.slack_webhook_url = "https://hooks.slack.com/secret"

    # Save should encrypt
    ConfigManager.save_config(phone, cfg)

    # Inspect raw file
    raw_path = os.path.join(users_dir, f"{phone}_config.json")
    with open(raw_path, "r") as f:
        raw_data = json.load(f)

    # Ensure it's encrypted on disk
    raw_tg = raw_data["channels"]["telegram_bot_token"]
    raw_slack = raw_data["channels"]["slack_webhook_url"]
    
    assert raw_tg != "TELEGRAM_SECRET_123"
    assert raw_slack != "https://hooks.slack.com/secret"
    assert raw_tg.startswith("gAAAAA")
    assert raw_slack.startswith("gAAAAA")

    # Load should decrypt
    loaded_cfg = ConfigManager.load_config(phone)
    assert loaded_cfg.channels.telegram_bot_token == "TELEGRAM_SECRET_123"
    assert loaded_cfg.channels.slack_webhook_url == "https://hooks.slack.com/secret"

def test_plaintext_fallback_when_no_key(monkeypatch, tmp_path):
    users_dir = tmp_path / "data" / "users"
    monkeypatch.setattr("src.core.config.USERS_DIR", str(users_dir))
    
    # No fernet key
    monkeypatch.setattr("src.core.config.get_fernet_key", lambda: None)

    phone = "918888888888"
    cfg = UserConfig()
    cfg.channels.telegram_bot_token = "PLAINTEXT_TOK_"

    ConfigManager.save_config(phone, cfg)

    raw_path = os.path.join(users_dir, f"{phone}_config.json")
    with open(raw_path, "r") as f:
        raw_data = json.load(f)

    assert raw_data["channels"]["telegram_bot_token"] == "PLAINTEXT_TOK_"

    loaded = ConfigManager.load_config(phone)
    assert loaded.channels.telegram_bot_token == "PLAINTEXT_TOK_"
