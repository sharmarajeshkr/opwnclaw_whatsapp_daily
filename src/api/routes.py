"""
src/api/routes.py
-----------------
FastAPI router — all REST endpoint handlers for OpenClaw.

Auth Endpoints:
  POST   /api/auth/register           - Self-serve user registration (phone + pin)
  POST   /api/auth/login              - Login (admin or user), returns role + token

User Endpoints:
  GET    /api/users                   - List all users + status  [Admin]
  DELETE /api/users/{phone}           - Delete a user            [Admin]
  GET    /api/users/{phone}/status    - Pairing + running status
  GET    /api/users/{phone}/config    - Get user config
  PUT    /api/users/{phone}/config    - Save user config
  GET    /api/users/{phone}/qr/image  - Serve QR PNG for scanning
  GET    /api/users/{phone}/qr/poll   - Poll pairing state (for UI polling)
  POST   /api/users/{phone}/qr        - Re-trigger QR generation
  POST   /api/users/{phone}/start     - Start bot
  POST   /api/users/{phone}/stop      - Stop bot
  GET    /api/users/{phone}/session   - Active interview session
  GET    /api/users/{phone}/performance - Performance stats

System Endpoints:
  POST   /api/system/start-all        - Start all bots  [Admin]
  POST   /api/system/stop-all         - Stop all bots   [Admin]
  GET    /api/system/logs             - Tail bot log    [Admin]
  GET    /health                      - Health check
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from src.core.config import ConfigManager, UserConfig, TopicsConfig, ChannelsConfig
from src.core.sys_config import settings
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


# ── Request / Response Models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str          # e.g. "919789824976" or "+919789824976"
    pin: str            # 4-digit PIN chosen by user


class LoginRequest(BaseModel):
    phone: Optional[str] = None   # empty / omitted → admin login
    password: str                 # admin password OR user pin


class ConfigUpdateRequest(BaseModel):
    schedule_time: Optional[str] = None
    timezone: Optional[str] = None
    pin: Optional[str] = None
    topics: Optional[dict] = None
    channels: Optional[dict] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_phone(raw: str) -> str:
    return raw.strip().lstrip("+")


def _require_user(phone: str) -> None:
    if phone not in ConfigManager.get_all_users():
        raise HTTPException(status_code=404, detail=f"User +{phone} not found.")


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@router.post("/api/auth/register", tags=["Auth"], status_code=201)
def register_user(body: RegisterRequest):
    """
    Self-serve user registration.
    Creates a new profile with the given phone number and PIN.
    Does NOT start QR automatically — the UI should call /qr next.
    """
    phone = _clean_phone(body.phone)
    if not phone.isdigit() or len(phone) < 8:
        raise HTTPException(status_code=422, detail="Phone number must be digits with country code (min 8 digits).")
    if not body.pin:
        raise HTTPException(status_code=422, detail="PIN is required.")
    if phone in ConfigManager.get_all_users():
        raise HTTPException(status_code=409, detail=f"+{phone} is already registered. Please login.")

    default_channels = ChannelsConfig(whatsapp_target=phone)
    new_cfg = UserConfig(channels=default_channels, pin_code=body.pin)
    ConfigManager.save_config(phone, new_cfg)

    return {
        "message": f"Account for +{phone} created. Call POST /api/users/{phone}/qr to begin WhatsApp pairing.",
        "phone": phone,
        "next_step": f"/api/users/{phone}/qr",
    }


@router.post("/api/auth/login", tags=["Auth"])
def login(body: LoginRequest):
    """
    Login endpoint.
    - Empty/missing phone → Admin login (checks ADMIN_PASSWORD).
    - With phone → User login (checks pin against stored config).
    Returns the role and phone on success.
    """
    if not body.phone or not body.phone.strip():
        # Admin login
        admin_pass = settings.ADMIN_PASSWORD
        if not admin_pass or body.password != admin_pass:
            raise HTTPException(status_code=401, detail="Invalid admin password.")
        return {"role": "ADMIN", "phone": None, "message": "Admin login successful."}

    phone = _clean_phone(body.phone)
    users = ConfigManager.get_all_users()
    if phone not in users:
        raise HTTPException(status_code=404, detail="Phone number not registered.")

    cfg = ConfigManager.load_config(phone)
    if body.password != getattr(cfg, "pin_code", "0000"):
        raise HTTPException(status_code=401, detail="Incorrect PIN.")

    paired = is_user_paired(phone)
    running = is_bot_running(phone)

    # Auto-start bot if paired but idle
    if paired and not running:
        start_bot(phone)

    return {
        "role": "USER",
        "phone": phone,
        "paired": paired,
        "bot_running": running or paired,  # will be running after auto-start
        "message": "Login successful.",
        "next_step": None if paired else f"/api/users/{phone}/qr",
    }


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
def health():
    """Health check — no auth required."""
    return {"status": "ok", "service": "OpenClaw API"}


# ── User List ─────────────────────────────────────────────────────────────────

@router.get("/api/users", tags=["Users"])
def list_users():
    """Return all registered users with their current status. [Admin]"""
    users = ConfigManager.get_all_users()
    return {
        "count": len(users),
        "users": [get_user_status(u) for u in users],
    }


@router.delete("/api/users/{phone}", tags=["Users"])
def remove_user(phone: str):
    """Delete a user and all associated data. [Admin]"""
    phone = _clean_phone(phone)
    _require_user(phone)
    if is_bot_running(phone):
        stop_bot(phone)
    delete_user_data(phone)
    return {"message": f"+{phone} deleted successfully."}


# ── User Status ───────────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/status", tags=["Users"])
def user_status(phone: str):
    """Get the current pairing and running status for a single user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    return get_user_status(phone)


# ── QR Endpoints ──────────────────────────────────────────────────────────────

@router.post("/api/users/{phone}/qr", tags=["QR Pairing"])
def trigger_qr(phone: str):
    """
    Trigger QR code generation for a user.
    Call this after registration. The QR image will be available at /qr/image
    within ~3 seconds.
    """
    phone = _clean_phone(phone)
    _require_user(phone)

    if is_user_paired(phone):
        raise HTTPException(status_code=409, detail=f"+{phone} is already paired.")

    trigger_qr_script(phone)
    return {
        "message": f"QR generation started for +{phone}. Poll /api/users/{phone}/qr/poll for status.",
        "qr_image_url": f"/api/users/{phone}/qr/image",
        "poll_url": f"/api/users/{phone}/qr/poll",
    }


@router.get("/api/users/{phone}/qr/image", tags=["QR Pairing"])
def get_qr_image(phone: str):
    """
    Serve the QR code PNG for a user.
    Returns 200 with image/png if the QR is ready, 404 if not yet generated.
    The UI should poll /qr/poll and display this image once ready.
    """
    phone = _clean_phone(phone)
    _require_user(phone)

    qr_path = os.path.join("data", f"qr_{phone}.png")
    if not os.path.exists(qr_path):
        raise HTTPException(
            status_code=404,
            detail="QR not ready yet. Trigger /api/users/{phone}/qr first, then retry in 3-5 seconds."
        )
    return FileResponse(qr_path, media_type="image/png", filename=f"qr_{phone}.png")


@router.get("/api/users/{phone}/qr/poll", tags=["QR Pairing"])
def poll_qr_status(phone: str):
    """
    Poll-friendly endpoint for the UI to check pairing progress.

    States returned:
      - "pending_qr"  → QR image is generating, not ready yet
      - "scan_ready"  → QR PNG exists, user should scan now
      - "paired"      → Device is paired, bot is (or will be) running
    """
    phone = _clean_phone(phone)
    _require_user(phone)

    qr_path = os.path.join("data", f"qr_{phone}.png")
    paired = is_user_paired(phone)
    qr_exists = os.path.exists(qr_path)

    if paired:
        # Ensure bot starts automatically once paired
        if not is_bot_running(phone):
            start_bot(phone)
        return {
            "state": "paired",
            "paired": True,
            "bot_running": True,
            "message": "Device paired! Bot is running."
        }
    elif qr_exists:
        return {
            "state": "scan_ready",
            "paired": False,
            "qr_image_url": f"/api/users/{phone}/qr/image",
            "message": "QR is ready. Open WhatsApp → Linked Devices → scan."
        }
    else:
        return {
            "state": "pending_qr",
            "paired": False,
            "message": "QR is being generated. Retry in 3 seconds."
        }


# ── Config Endpoints ──────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/config", tags=["Config"])
def get_config(phone: str):
    """Get the full configuration for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    cfg = ConfigManager.load_config(phone)
    data = cfg.model_dump()
    # Never expose the pin in GET responses
    data.pop("pin_code", None)
    return data


@router.put("/api/users/{phone}/config", tags=["Config"])
def update_config(phone: str, body: ConfigUpdateRequest):
    """
    Update configuration for a user. Only provided fields are changed.
    Supports: schedule_time, timezone, pin, topics (dict), channels (dict).
    """
    phone = _clean_phone(phone)
    _require_user(phone)

    cfg = ConfigManager.load_config(phone)
    cfg_dict = cfg.model_dump()

    if body.schedule_time is not None:
        cfg_dict["schedule_time"] = body.schedule_time
    if body.timezone is not None:
        cfg_dict["timezone"] = body.timezone
    if body.pin is not None:
        cfg_dict["pin_code"] = body.pin
    if body.topics is not None:
        cfg_dict["topics"].update(body.topics)
    if body.channels is not None:
        cfg_dict["channels"].update(body.channels)

    updated = UserConfig.model_validate(cfg_dict)
    ConfigManager.save_config(phone, updated)

    result = updated.model_dump()
    result.pop("pin_code", None)
    return {"message": f"Config updated for +{phone}.", "config": result}


# ── Bot Control ───────────────────────────────────────────────────────────────

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


# ── Session ───────────────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/session", tags=["Session"])
def get_session(phone: str):
    """Get the current active interview session / pending question for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    session = SessionManager.get_active_session(phone)
    if not session:
        return {"active": False, "message": "No active question pending.", "session": None}
    return {"active": True, "session": session}


# ── Performance ───────────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/performance", tags=["Performance"])
def get_performance(phone: str):
    """Get all-time performance statistics for a user."""
    phone = _clean_phone(phone)
    _require_user(phone)
    perf = PerformanceTracker.get_all_time_summary(phone)
    return {"performance": perf, "total_topics_scored": len(perf)}


# ── System [Admin] ────────────────────────────────────────────────────────────

@router.post("/api/system/start-all", tags=["System"])
def start_all():
    """Start all paired bots via the main daemon. [Admin]"""
    start_all_bots()
    return {"message": "All bot processes triggered."}


@router.post("/api/system/stop-all", tags=["System"])
def stop_all():
    """Stop all running bot processes. [Admin]"""
    stop_all_bots()
    return {"message": "All bot processes terminated."}


@router.get("/api/system/logs", tags=["System"])
def get_logs(lines: int = Query(default=100, ge=1, le=1000)):
    """Tail the bot log file. Returns the last N lines (default 100). [Admin]"""
    log_path = os.path.join("data", "bot.log")
    if not os.path.exists(log_path):
        return {"lines": [], "message": "Log file not found."}
    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return {
        "total_lines": len(all_lines),
        "returned_lines": min(lines, len(all_lines)),
        "lines": [ln.rstrip() for ln in all_lines[-lines:]],
    }
