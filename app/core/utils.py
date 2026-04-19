"""
app/core/utils.py
-----------------
Shared helper utilities for process management, orchestration, and logging context.
All process management uses `psutil` for platform independence.
"""

import os
import sys
import time
import signal
import asyncio
import logging
import functools
import subprocess
from typing import Optional, Any, Callable
import psutil

from app.core.config import ConfigManager
from app.core.logging import get_logger

logger = get_logger("Utils")

# ── Logging Context & Performance ─────────────────────────────────────────────

class ContextAdapter(logging.LoggerAdapter):
    """Standardizes log context (e.g. phone number) across modules."""
    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).update(self.extra)
        context_str = f"[{self.extra.get('phone', 'Global')}] "
        return f"{context_str}{msg}", kwargs


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
    """Delete all database and on-disk data associated with a user."""
    from app.database.db import get_conn
    stop_bot(phone_number)
    
    # 1. Soft Delete in Database
    with get_conn() as conn:
        # Mark as inactive and un-paired
        conn.execute(
            "UPDATE user_status SET is_active = FALSE, is_paired = FALSE, updated_at = CURRENT_TIMESTAMP "
            "WHERE phone_number = %s", 
            (phone_number,)
        )
        # Clear active interview sessions so reactivation starts fresh
        conn.execute("DELETE FROM sessions WHERE phone_number = %s", (phone_number,))

    # 2. Filesystem Cleanup (Temporary Artifacts)
    users_dir = os.path.join("data", "users")
    paths = [
        os.path.join(users_dir, f"pair_{phone_number}.py"),     # One-shot Pairing Script
        os.path.join("data", f"qr_{phone_number}.png"),         # QR Image
    ]
    
    for p in paths:
        if os.path.exists(p):
            try:
                os.remove(p)
                logger.info(f"Deleted file artifact: {p}")
            except Exception as e:
                logger.warning(f"Could not delete {p}: {e}")

# ── Pairing Detection ─────────────────────────────────────────────────────────

def is_user_paired(phone: str) -> bool:
    """Check if a user is paired by querying the user_status table."""
    from app.database.db import get_conn
    with get_conn() as conn:
        row = conn.execute("SELECT is_paired FROM user_status WHERE phone_number = %s", (phone,)).fetchone()
    return row["is_paired"] if row else False

# ── QR / Pairing Script ───────────────────────────────────────────────────────

def _generate_pair_script(phone_number: str) -> str:
    """Returns the source code for the one-shot pairing script."""
    return (
        "import asyncio\n"
        "import os\n"
        "import sys\n"
        "\n"
        "sys.path.append(os.getcwd())\n"
        "\n"
        "from app.channels.whatsapp.client import WhatsAppClient\n"
        "\n"
        "async def main():\n"
        "    try:\n"
        f"        c = WhatsAppClient('{phone_number}')\n"
        "        await c.connect()\n"
        "        print('Connected! Sending welcome message...')\n"
        "        await asyncio.sleep(5)\n"
        "        try:\n"
        "            welcome = (\n"
        "                '🦞 *WELCOME TO OPENCLAW*\\n\\n'\n"
        "                'Your AI Interview Coach is now linked. Here is what to expect:\\n\\n'\n"
        "                '🔹 *Challenges*: Every morning at 06:00, I\\'ll send you a new architectural deep-dive.\\n'\n"
        "                '🔹 *Visuals*: Every challenge includes an AI-generated diagram to help you visualize the solution.\\n'\n"
        "                '🔹 *Feedback*: Reply to any message to start a mock interview and get scoring feedback.\\n\\n'\n"
        "                '_Type \\'HELP\\' anytime to see your current streak and mastery scores._'\n"
        "            )\n"
        "            await c.send_message(welcome)\n"
        "        except Exception as e:\n"
        "            print(f'Warning: could not send welcome message: {e}')\n"
        "        import subprocess, sys\n"
        f"        subprocess.Popen([sys.executable, 'main.py', '--phone', '{phone_number}'], cwd=os.getcwd(), start_new_session=True)\n"
        "        print('Bot daemon started.')\n"
        "        await asyncio.sleep(5)\n"
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

def trigger_qr_script(raw: str) -> None:
    """Write and execute a one-shot pairing script."""
    ConfigManager.load_config(raw)
    pair_script_path = os.path.join("data", "users", f"pair_{raw}.py")
    os.makedirs(os.path.dirname(pair_script_path), exist_ok=True)
    script_content = _generate_pair_script(raw)
    
    with open(pair_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

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
