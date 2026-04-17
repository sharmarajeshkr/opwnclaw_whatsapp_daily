"""
src/api/routes.py
-----------------
FastAPI router — all REST endpoint handlers for OpenClaw.

Endpoints:
  GET    /api/users                   - list all users + status
  POST   /api/users/register          - register new user & trigger QR
  DELETE /api/users/{phone}           - delete a user and all their data
  GET    /api/users/{phone}/config    - get user config
  PUT    /api/users/{phone}/config    - save user config
  GET    /api/users/{phone}/status    - get pairing + running status
  POST   /api/users/{phone}/start     - start bot for a user
  POST   /api/users/{phone}/stop      - stop bot for a user
  POST   /api/users/{phone}/qr        - re-trigger QR pairing
  GET    /api/system/logs             - tail the bot log
  GET    /health                      - health check
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.core.config import ConfigManager, UserConfig, TopicsConfig, ChannelsConfig
from src.core.performance import PerformanceTracker
from src.core.session import SessionManager
from src.core.utils import (
    is_bot_running,
    is_user_paired,
    start_bot,
    stop_bot,
    delete_user_data,
    trigger_qr_script,
    start_all_bots,
    stop_all_bots,
    get_user_status,
)

router = APIRouter()


# ── Request/Response Models ───────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str  # e.g. "919789824976" or "+919789824976"


class ConfigUpdateRequest(BaseModel):
    schedule_time: Optional[str] = None
    topics: Optional[dict] = None
    channels: Optional[dict] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_phone(raw: str) -> str:
    return raw.strip().lstrip("+")


def _require_user(phone: str) -> None:
    if phone not in ConfigManager.get_all_users():
        raise HTTPException(status_code=404, detail=f"User +{phone} not found.")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "OpenClaw API"}


@router.get("/api/users", tags=["Users"])
def list_users():
    """Return all registered users with their current status."""
    users = ConfigManager.get_all_users()
    return {
        "count": len(users),
        "users": [get_user_status(u) for u in users],
    }


@router.post("/api/users/register", tags=["Users"], status_code=201)
def register_user(body: RegisterRequest):
    """Register a new user and trigger QR code generation."""
    phone = _clean_phone(body.phone)
    if len(phone) < 8:
        raise HTTPException(status_code=422, detail="Phone number too short.")

    existing = ConfigManager.get_all_users()
    if phone in existing and is_user_paired(phone):
        raise HTTPException(status_code=409, detail=f"+{phone} is already registered and paired.")

    trigger_qr_script(phone)
    return {
        "message": f"QR pairing initiated for +{phone}. Scan the QR code displayed in the dashboard.",
        "phone": phone,
    }


@router.delete("/api/users/{phone}", tags=["Users"])
def remove_user(phone: str):
    """Delete a user and all associated data (config, session, QR, history)."""
    phone = _clean_phone(phone)
    _require_user(phone)

    if is_bot_running(phone):
        stop_bot(phone)

    delete_user_data(phone)
    return {"message": f"+{phone} deleted successfully."}


@router.get("/api/users/{phone}/status", tags=["Users"])
def user_status(phone: str):
    """Get the current pairing and running status for a single user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    return get_user_status(phone)


@router.get("/api/users/{phone}/session", tags=["Session"])
def get_session(phone: str):
    """Get the current active interview session for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    
    session = SessionManager.get_active_session(phone)
    if not session:
        return {"active": False, "message": "No active question pending.", "session": None}
    
    return {"active": True, "session": session}


@router.get("/api/users/{phone}/performance", tags=["Performance"])
def get_performance(phone: str):
    """Get all-time performance statistics for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    
    perf = PerformanceTracker.get_all_time_summary(phone)
    return {"performance": perf, "total_topics_scored": len(perf)}


@router.get("/api/users/{phone}/config", tags=["Config"])
def get_config(phone: str):
    """Get the configuration for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    cfg = ConfigManager.load_config(phone)
    return cfg.model_dump()


@router.put("/api/users/{phone}/config", tags=["Config"])
def update_config(phone: str, body: ConfigUpdateRequest):
    """Update configuration for a user. Only provided fields are changed."""
    phone = _clean_phone(phone)
    _require_user(phone)

    cfg = ConfigManager.load_config(phone)
    cfg_dict = cfg.model_dump()

    if body.schedule_time is not None:
        cfg_dict["schedule_time"] = body.schedule_time
    if body.topics is not None:
        cfg_dict["topics"].update(body.topics)
    if body.channels is not None:
        cfg_dict["channels"].update(body.channels)

    updated = UserConfig.model_validate(cfg_dict)
    ConfigManager.save_config(phone, updated)
    return {"message": f"Config updated for +{phone}.", "config": updated.model_dump()}


@router.post("/api/users/{phone}/start", tags=["Control"])
def start_user_bot(phone: str):
    """Start the bot process for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)

    if not is_user_paired(phone):
        raise HTTPException(status_code=400, detail=f"+{phone} is not paired. Scan QR first.")
    if is_bot_running(phone):
        return {"message": f"Bot for +{phone} is already running."}

    start_bot(phone)
    return {"message": f"Bot started for +{phone}."}


@router.post("/api/users/{phone}/stop", tags=["Control"])
def stop_user_bot(phone: str):
    """Stop the bot process for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)

    if not is_bot_running(phone):
        return {"message": f"Bot for +{phone} is not running."}

    stop_bot(phone)
    return {"message": f"Bot stopped for +{phone}."}


@router.post("/api/users/{phone}/qr", tags=["Users"])
def regenerate_qr(phone: str):
    """Re-trigger QR pairing for a user (useful if QR expired)."""
    phone = _clean_phone(phone)
    _require_user(phone)
    trigger_qr_script(phone)
    return {"message": f"QR re-generation triggered for +{phone}."}


@router.post("/api/system/start-all", tags=["System"])
def start_all():
    """Start all paired bots via the main daemon."""
    start_all_bots()
    return {"message": "All bot processes triggered."}


@router.post("/api/system/stop-all", tags=["System"])
def stop_all():
    """Stop all running bot processes."""
    stop_all_bots()
    return {"message": "All bot processes terminated."}


@router.get("/api/system/logs", tags=["System"])
def get_logs(lines: int = Query(default=100, ge=1, le=1000)):
    """Tail the bot log file. Returns the last N lines (default 100)."""
    log_path = os.path.join("data", "bot.log")
    if not os.path.exists(log_path):
        return {"lines": [], "message": "Log file not found."}
    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return {
        "total_lines": len(all_lines),
        "returned_lines": min(lines, len(all_lines)),
        "lines": [l.rstrip() for l in all_lines[-lines:]],
    }
