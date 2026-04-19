"""
app/api/routes.py
-----------------
FastAPI router — all REST endpoint handlers for Interview.
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.core.config import ConfigManager, UserConfig, TopicsConfig, ChannelsConfig, settings
from app.services.performance_tracker import PerformanceTracker
from app.services.session_manager import SessionManager
from app.core.utils import (
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
    phone: str
    pin: str

class LoginRequest(BaseModel):
    phone: Optional[str] = None
    password: str

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
    phone = _clean_phone(body.phone)
    if not phone.isdigit() or len(phone) < 8:
        raise HTTPException(status_code=422, detail="Phone number must be digits with country code.")
    if not body.pin:
        raise HTTPException(status_code=422, detail="PIN is required.")
    if phone in ConfigManager.get_all_users():
        raise HTTPException(status_code=409, detail=f"+{phone} is already registered.")

    default_channels = ChannelsConfig(whatsapp_target=phone)
    new_cfg = UserConfig(channels=default_channels, pin_code=body.pin)
    ConfigManager.save_config(phone, new_cfg)

    return {
        "message": f"Account for +{phone} created.",
        "phone": phone
    }

@router.post("/api/auth/login", tags=["Auth"])
def login(body: LoginRequest):
    if not body.phone or not body.phone.strip():
        admin_pass = settings.ADMIN_PASSWORD
        if not admin_pass or body.password != admin_pass:
            raise HTTPException(status_code=401, detail="Invalid admin password.")
        return {"role": "ADMIN", "phone": None}

    phone = _clean_phone(body.phone)
    users = ConfigManager.get_all_users()
    if phone not in users:
        raise HTTPException(status_code=404, detail="Phone number not registered.")

    cfg = ConfigManager.load_config(phone)
    if body.password != getattr(cfg, "pin_code", "0000"):
        raise HTTPException(status_code=401, detail="Incorrect PIN.")

    paired = is_user_paired(phone)
    if paired and not is_bot_running(phone):
        start_bot(phone)

    return {
        "role": "USER",
        "phone": phone,
        "paired": paired,
        "bot_running": is_bot_running(phone) or paired
    }

# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "Interview API"}

# ── User List ─────────────────────────────────────────────────────────────────

@router.get("/api/users", tags=["Users"])
def list_users():
    users = ConfigManager.get_all_users()
    return {
        "count": len(users),
        "users": [get_user_status(u) for u in users],
    }

@router.delete("/api/users/{phone}", tags=["Users"])
def remove_user(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    delete_user_data(phone)
    return {"message": f"+{phone} deleted successfully."}

# ── User Status ───────────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/status", tags=["Users"])
def user_status_endpoint(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    return get_user_status(phone)

# ── QR Endpoints ──────────────────────────────────────────────────────────────

@router.post("/api/users/{phone}/qr", tags=["QR Pairing"])
def trigger_qr(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    if is_user_paired(phone):
        raise HTTPException(status_code=409, detail=f"+{phone} is already paired.")
    trigger_qr_script(phone)
    return {"message": "QR generation started."}

@router.get("/api/users/{phone}/qr/image", tags=["QR Pairing"])
def get_qr_image(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    qr_path = os.path.join("data", f"qr_{phone}.png")
    if not os.path.exists(qr_path):
        raise HTTPException(status_code=404, detail="QR not ready.")
    return FileResponse(qr_path, media_type="image/png")

@router.get("/api/users/{phone}/qr/poll", tags=["QR Pairing"])
def poll_qr_status(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    paired = is_user_paired(phone)
    if paired:
        if not is_bot_running(phone):
            start_bot(phone)
        return {"state": "paired", "paired": True}
    elif os.path.exists(os.path.join("data", f"qr_{phone}.png")):
        return {"state": "scan_ready", "paired": False}
    else:
        return {"state": "pending_qr", "paired": False}

# ── Config Endpoints ──────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/config", tags=["Config"])
def get_config(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    cfg = ConfigManager.load_config(phone)
    data = cfg.model_dump()
    data.pop("pin_code", None)
    return data

@router.put("/api/users/{phone}/config", tags=["Config"])
def update_config(phone: str, body: ConfigUpdateRequest):
    phone = _clean_phone(phone)
    _require_user(phone)
    cfg = ConfigManager.load_config(phone)
    cfg_dict = cfg.model_dump()
    if body.schedule_time is not None: cfg_dict["schedule_time"] = body.schedule_time
    if body.timezone is not None: cfg_dict["timezone"] = body.timezone
    if body.pin is not None: cfg_dict["pin_code"] = body.pin
    if body.topics is not None: cfg_dict["topics"].update(body.topics)
    if body.channels is not None: cfg_dict["channels"].update(body.channels)
    updated = UserConfig.model_validate(cfg_dict)
    ConfigManager.save_config(phone, updated)
    return {"message": "Config updated."}

# ── Bot Control ───────────────────────────────────────────────────────────────

@router.post("/api/users/{phone}/start", tags=["Control"])
def start_user_bot(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    if not is_user_paired(phone):
        raise HTTPException(status_code=400, detail="Not paired.")
    start_bot(phone)
    return {"message": "Bot started."}

@router.post("/api/users/{phone}/stop", tags=["Control"])
def stop_user_bot(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    stop_bot(phone)
    return {"message": "Bot stopped."}

# ── Session ───────────────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/session", tags=["Session"])
def get_session(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    session = SessionManager.get_active_session(phone)
    return {"active": bool(session), "session": session}

# ── Performance ───────────────────────────────────────────────────────────────

@router.get("/api/users/{phone}/performance", tags=["Performance"])
def get_performance(phone: str):
    phone = _clean_phone(phone)
    _require_user(phone)
    return {"performance": PerformanceTracker.get_all_time_summary(phone)}

# ── System [Admin] ────────────────────────────────────────────────────────────

@router.post("/api/system/start-all", tags=["System"])
def start_all():
    start_all_bots()
    return {"message": "System started."}

@router.post("/api/system/stop-all", tags=["System"])
def stop_all():
    stop_all_bots()
    return {"message": "System stopped."}

@router.get("/api/system/logs", tags=["System"])
def get_logs(lines: int = Query(default=100, ge=1, le=1000)):
    log_path = os.path.join("logs", "main.log")
    if not os.path.exists(log_path):
        return {"lines": [], "message": "Log file not found."}
    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return {"lines": [ln.rstrip() for ln in all_lines[-lines:]]}
