import pytest
import psycopg2
from cryptography.fernet import Fernet
from src.core.config import ConfigManager, UserConfig
from src.core.sys_config import settings

@pytest.fixture(autouse=True)
def isolated_db():
    settings.POSTGRES_DB = "openclaw_test"
    from src.core.db import init_db
    init_db()
    
    from src.core.db import get_conn
    yield get_conn()

    # Teardown
    dsn = settings.get_database_url()
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE user_configs, user_history, user_status RESTART IDENTITY CASCADE")
    cur.close()
    conn.close()

def test_fernet_encryption_works():
    # Generate a dummy key
    key = Fernet.generate_key().decode("utf-8")
    settings.FERNET_KEY = key

    phone = "919999999999"
    cfg = UserConfig()
    cfg.channels.telegram_bot_token = "TELEGRAM_SECRET_123"
    cfg.channels.slack_webhook_url = "https://hooks.slack.com/secret"

    # Save should encrypt into DB
    ConfigManager.save_config(phone, cfg)

    # Inspect raw DB row
    from src.core.db import get_conn
    with get_conn() as conn:
        row = conn.execute("SELECT channels FROM user_configs WHERE phone_number = %s", (phone,)).fetchone()
    
    channels = row["channels"]
    raw_tg = channels["telegram_bot_token"]
    raw_slack = channels["slack_webhook_url"]
    
    assert raw_tg != "TELEGRAM_SECRET_123"
    assert raw_slack != "https://hooks.slack.com/secret"
    assert raw_tg.startswith("gAAAAA")
    assert raw_slack.startswith("gAAAAA")

    # Load should decrypt
    loaded_cfg = ConfigManager.load_config(phone)
    assert loaded_cfg.channels.telegram_bot_token == "TELEGRAM_SECRET_123"
    assert loaded_cfg.channels.slack_webhook_url == "https://hooks.slack.com/secret"

def test_plaintext_fallback_when_no_key():
    # No fernet key
    settings.FERNET_KEY = None

    phone = "918888888888"
    cfg = UserConfig()
    cfg.channels.telegram_bot_token = "PLAINTEXT_TOK_"

    ConfigManager.save_config(phone, cfg)

    from src.core.db import get_conn
    with get_conn() as conn:
        row = conn.execute("SELECT channels FROM user_configs WHERE phone_number = %s", (phone,)).fetchone()
    
    assert row["channels"]["telegram_bot_token"] == "PLAINTEXT_TOK_"

    loaded = ConfigManager.load_config(phone)
    assert loaded.channels.telegram_bot_token == "PLAINTEXT_TOK_"
