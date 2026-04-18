"""
src/core/utils.py
-----------------
Shared helper utilities used by both the Streamlit dashboard (app.py)
and the FastAPI server (api.py).

All process management uses `psutil` for platform independence —
works on Windows, Linux, and macOS.
"""
import os
import sys
import signal
import subprocess
from typing import Optional
import psutil

from src.core.config import ConfigManager
from src.core.logger import get_logger

logger = get_logger("Utils")

# ── Python / venv resolution ──────────────────────────────────────────────────

def _python_exe() -> str:
    """Return the virtual-env python executable (cross-platform)."""
    if sys.platform == "win32":
        exe = os.path.join("venv", "Scripts", "python.exe")
    else:
        exe = os.path.join("venv", "bin", "python")
    return exe if os.path.exists(exe) else sys.executable


# ── Process Management ────────────────────────────────────────────────────────

def _find_processes(cmdline_fragment: str) -> list:
    """Return psutil.Process objects whose cmdline contains the fragment."""
    matches = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if cmdline_fragment in cmdline:
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return matches


def is_bot_running(phone_number: str) -> bool:
    """Return True if a bot process is running for the given phone number."""
    return len(_find_processes(f"main.py --phone {phone_number}")) > 0


def start_bot(phone_number: str) -> None:
    """Start a detached bot process for the given phone number."""
    subprocess.Popen(
        [_python_exe(), "main.py", "--phone", phone_number],
        cwd=os.getcwd(),
        start_new_session=True,
    )
    logger.info(f"Started bot for +{phone_number}")


def stop_bot(phone_number: str) -> None:
    """Kill the bot process for the given phone number."""
    procs = _find_processes(f"main.py --phone {phone_number}")
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=5)
            logger.info(f"Stopped bot for +{phone_number} (pid={p.pid})")
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass


def start_all_bots() -> None:
    """Launch the main.py daemon (manages all paired users)."""
    subprocess.Popen(
        [_python_exe(), "main.py"],
        cwd=os.getcwd(),
        start_new_session=True,
    )
    logger.info("Started main daemon (all bots)")


def stop_all_bots() -> None:
    """Kill all running bot processes (main.py daemon + per-user bots)."""
    procs = _find_processes("main.py")
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=5)
            logger.info(f"Stopped process pid={p.pid}")
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass


def delete_user_data(phone_number: str) -> None:
    """Delete all on-disk data associated with a user."""
    # Stop the bot if it's currently running to release SQLite file locks
    stop_bot(phone_number)
    
    paths = [
        ConfigManager.get_config_path(phone_number),
        os.path.join("data", "users", f"{phone_number}.sqlite3"),
        os.path.join("data", f"qr_{phone_number}.png"),
        os.path.join("data", "history", f"{phone_number}.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                logger.warning(f"Could not delete {p}: {e}")


# ── Pairing Detection ─────────────────────────────────────────────────────────

def is_user_paired(phone: str) -> bool:
    """
    Check if a user is paired. The sqlite3 session file is created immediately
    by neonize, so we can't just check its existence. If the qr png is present
    or missing completely without the DB, they are not paired.
    """
    session_path = os.path.join("data", "users", f"{phone}.sqlite3")
    qr_path = os.path.join("data", f"qr_{phone}.png")

    session_exists = os.path.exists(session_path)

    # A user is paired only if their session file exists AND they don't have a pending QR scan.
    return session_exists and not os.path.exists(qr_path)


# ── QR / Pairing Script ───────────────────────────────────────────────────────

def trigger_qr_script(raw: str) -> None:
    """
    Write and execute a one-shot pairing script for the given phone number.
    The script connects via neonize, which triggers the QR event, saves the
    PNG, and then waits for a ConnectedEv before cleaning up.
    """
    ConfigManager.load_config(raw)  # ensure config exists with defaults

    pair_script_path = os.path.join("data", "users", f"pair_{raw}.py")
    script_content = (
        "import asyncio\n"
        "import os\n"
        "import sys\n"
        "\n"
        "sys.path.append(os.getcwd())\n"
        "\n"
        "from src.bot.client import WhatsAppClient\n"
        "\n"
        "async def main():\n"
        "    try:\n"
        f"        c = WhatsAppClient('{raw}')\n"
        "        await c.connect()\n"
        "        # Wait explicitly for the multi-device sync to finish before dropping the websocket\n"
        "        print('Connected! Allowing 30 seconds for crypto sync...')\n"
        "        await asyncio.sleep(30)\n"
        "    finally:\n"
        "        try:\n"
        "            os.remove(__file__)\n"
        "        except Exception:\n"
        "            pass\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    loop = asyncio.new_event_loop()\n"
        "    asyncio.set_event_loop(loop)\n"
        "    loop.run_until_complete(main())\n"
    )
    with open(pair_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # Kill any existing pairing process for this number
    old_procs = _find_processes(f"pair_{raw}.py")
    for p in old_procs:
        try:
            p.terminate()
        except psutil.NoSuchProcess:
            pass

    subprocess.Popen(
        [_python_exe(), pair_script_path],
        cwd=os.getcwd(),
        start_new_session=True,
    )
    logger.info(f"QR pairing script launched for +{raw}")


# ── User Status Dict ──────────────────────────────────────────────────────────

def get_user_status(phone: str) -> dict:
    """Return a status dict for a single user."""
    paired = is_user_paired(phone)
    running = is_bot_running(phone)
    qr_path = os.path.join("data", f"qr_{phone}.png")
    cfg = ConfigManager.load_config(phone)
    return {
        "phone": phone,
        "paired": paired,
        "running": running,
        "qr_pending": os.path.exists(qr_path),
        "schedule_time": cfg.schedule_time,
        "topics": cfg.topics.model_dump(),
    }
