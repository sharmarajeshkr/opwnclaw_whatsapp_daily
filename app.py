import streamlit as st
import subprocess
import datetime
import os
import json
import time
from src.core.config import ConfigManager, UserConfig
from src.core.logger import get_logger

logger = get_logger("StreamlitApp")

st.set_page_config(
    page_title="OpenClaw Bot Configurator",
    page_icon="🦀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }

/* Dark glassmorphism cards */
.glass-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 16px;
    padding: 1.5rem;
    backdrop-filter: blur(8px);
    margin-bottom: 1rem;
}

/* User profile card */
.user-card {
    background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(168,85,247,0.15) 100%);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.75rem;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.user-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(99,102,241,0.25);
}

/* Status badges */
.badge-active {
    background: rgba(34,197,94,0.2);
    color: #4ade80;
    border: 1px solid rgba(34,197,94,0.4);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.78rem;
    font-weight: 600;
}
.badge-pending {
    background: rgba(251,191,36,0.2);
    color: #fbbf24;
    border: 1px solid rgba(251,191,36,0.4);
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.78rem;
    font-weight: 600;
}

/* Header gradient */
.hero-title {
    background: linear-gradient(135deg, #818cf8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}
.hero-sub {
    color: rgba(255,255,255,0.5);
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* QR container */
.qr-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: rgba(255,255,255,0.03);
    border: 1px dashed rgba(99,102,241,0.4);
    border-radius: 16px;
    padding: 2rem;
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown('<p class="hero-title">🦀 OpenClaw — Multi-User Bot Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">Manage WhatsApp delivery profiles and schedules for each user.</p>', unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_profiles, tab_config, tab_control, tab_logs = st.tabs([
    "👥 User Profiles",
    "⚙️ Configure User",
    "🚀 System Control",
    "📜 Logs",
])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — USER PROFILES
# ────────────────────────────────────────────────────────────────────────────
with tab_profiles:
    st.subheader("Registered Users")

    users = ConfigManager.get_all_users()

    if users:
        for phone in users:
            cfg = ConfigManager.load_config(phone)
            sched = cfg.schedule_time if cfg.schedule_time else "—"
            topics = cfg.topics
            active_topics = [v for k, v in topics.model_dump().items() if v]
            topic_list = ", ".join(active_topics)
            qr_path = os.path.join("data", f"qr_{phone}.png")
            paired = not os.path.exists(qr_path)

            col_info, col_badge = st.columns([5, 1])
            with col_info:
                st.markdown(f"""
                <div class="user-card">
                    <strong>📱 +{phone}</strong> &nbsp;&nbsp;
                    <span style="color:rgba(255,255,255,0.5);font-size:0.85rem;">Daily @ {sched}</span><br>
                    <span style="color:rgba(255,255,255,0.45);font-size:0.8rem;">{topic_list}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_badge:
                st.markdown("<br>", unsafe_allow_html=True)
                if paired:
                    st.markdown('<span class="badge-active">● Paired</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge-pending">◌ Scan QR</span>', unsafe_allow_html=True)
    else:
        st.info("No users registered yet.")

    st.divider()

    st.subheader("➕ Register New User")
    with st.form("new_user_form", clear_on_submit=True):
        col_ph, col_btn = st.columns([3, 1])
        with col_ph:
            new_phone = st.text_input(
                "Mobile Number (with country code)",
                placeholder="+919876543210",
                label_visibility="collapsed",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            register_btn = st.form_submit_button("Generate QR", type="primary", use_container_width=True)

        if register_btn:
            raw = new_phone.strip().lstrip("+")
            if len(raw) < 8:
                st.error("Please enter a valid number.")
            elif raw in users:
                st.warning(f"+{raw} is already registered.")
            else:
                # Triggers user config creation
                ConfigManager.load_config(raw)
                # Background subprocess to capture QR code
                subprocess.Popen(
                    ["powershell", "-Command",
                     f'Start-Process -NoNewWindow .\\venv\\Scripts\\python.exe '
                     f'-ArgumentList "-c","from src.bot.client import WhatsAppClient; '
                     f'import asyncio; c = WhatsAppClient(chr(39)+{raw!r}+chr(39)); asyncio.run(c.connect())"'],
                )
                st.success(f"✅ Initializing registration for +{raw}. QR will appear shortly.")
                time.sleep(3)
                st.rerun()

    # QR Display
    pending_qr_users = [
        u for u in ConfigManager.get_all_users()
        if os.path.exists(os.path.join("data", f"qr_{u}.png"))
    ]
    if pending_qr_users:
        st.subheader("📷 Pending QR Codes — Scan to Pair")
        for u in pending_qr_users:
            qr_path = os.path.join("data", f"qr_{u}.png")
            st.markdown(f"**+{u}** — Scan in WhatsApp → Linked Devices")
            st.image(qr_path, caption=f"QR for +{u}", width=280)
            
            col_ref, col_del = st.columns([1, 1])
            with col_ref:
                if st.button(f"🔄 Refresh QR +{u}", key=f"r_{u}"):
                    st.rerun()
            with col_del:
                if st.button(f"🗑️ Delete User +{u}", key=f"d_{u}"):
                    if os.path.exists(ConfigManager.get_config_path(u)):
                         os.remove(ConfigManager.get_config_path(u))
                    if os.path.exists(qr_path):
                         os.remove(qr_path)
                    st.rerun()

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — CONFIGURE USER
# ────────────────────────────────────────────────────────────────────────────
with tab_config:
    st.subheader("⚙️ Per-User Configuration")

    all_users = ConfigManager.get_all_users()
    if not all_users:
        st.warning("Please register a user first.")
    else:
        selected_user = st.selectbox(
            "Select User to Configure",
            options=all_users,
            format_func=lambda x: f"+{x}",
        )

        config = ConfigManager.load_config(selected_user)

        with st.form("user_config_form"):
            col_s1, col_s2, col_s3 = st.columns([1, 1, 1])
            with col_s1:
                t_hour, t_min = map(int, config.schedule_time.split(":"))
                schedule = st.time_input("Daily Delivery Time", value=datetime.time(t_hour, t_min))
            with col_s2:
                sl_hook = st.text_input("Slack Webhook URL", value=config.channels.slack_webhook_url)
            with col_s3:
                tg_token = st.text_input("Telegram Bot Token", value=config.channels.telegram_bot_token)

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                tg_chat = st.text_input("Telegram Chat ID", value=config.channels.telegram_chat_id)

            st.markdown("---")
            st.subheader("📚 Content Sequence Topics")
            col_c1, col_c2 = st.columns(2)
                
            with col_c1:
                t1 = st.text_input("1. Architecture Challenge", value=config.topics.topic_1)
                t2 = st.text_input("2. Deep Dive Subject 1", value=config.topics.topic_2)
                t3 = st.text_input("3. Deep Dive Subject 2", value=config.topics.topic_3)
            with col_c2:
                t4 = st.text_input("4. Fresh Updates 1", value=config.topics.topic_4)
                t5 = st.text_input("5. Fresh Updates 2", value=config.topics.topic_5)
                st.markdown("<br>", unsafe_allow_html=True)
                save_btn = st.form_submit_button("💾 Save User Configuration", type="primary", use_container_width=True)

            if save_btn:
                new_cfg = UserConfig(
                    schedule_time=schedule.strftime("%H:%M"),
                    topics={
                        "topic_1": t1, "topic_2": t2, "topic_3": t3,
                        "topic_4": t4, "topic_5": t5,
                    },
                    channels={
                        "whatsapp_target": selected_user,
                        "telegram_bot_token": tg_token,
                        "telegram_chat_id": tg_chat,
                        "slack_webhook_url": sl_hook,
                    }
                )
                ConfigManager.save_config(selected_user, new_cfg)
                st.success(f"✅ Saved for +{selected_user}! Restart bot component to apply.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 3 — SYSTEM CONTROL
# ────────────────────────────────────────────────────────────────────────────
with tab_control:
    st.subheader("🚀 Daemon Orchestration")
    st.markdown("Manage the multi-user background bot process.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Start Bot Daemon", use_container_width=True):
            subprocess.Popen([
                "powershell", "-Command",
                "Start-Process -NoNewWindow .\\venv\\Scripts\\python.exe main.py"
            ])
            st.success("✅ Main bot daemon triggered.")
    with col2:
        if st.button("🛑 Stop Active Bots", use_container_width=True):
            subprocess.run(
                'powershell -Command "Get-Process -Name python -ErrorAction SilentlyContinue '
                '| Where-Object { $_.CommandLine -match \'main.py\' } | Stop-Process -Force"',
                shell=True,
            )
            st.warning("⏺️ Terminated bot processes.")

    st.divider()
    all_u = ConfigManager.get_all_users()
    if all_u:
        rows = []
        for u in all_u:
            c = ConfigManager.load_config(u)
            rows.append({
                "User": f"+{u}",
                "Delivery Time": c.schedule_time,
                "Status": "Ready" if not os.path.exists(os.path.join("data", f"qr_{u}.png")) else "Awaiting Pair"
            })
        st.dataframe(rows, use_container_width=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 4 — LOGS
# ────────────────────────────────────────────────────────────────────────────
with tab_logs:
    st.subheader("📜 System Logs")
    if st.button("刷新", id="refresh_btn"):
        pass

    log_path = os.path.join("data", "bot.log")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        st.code("".join(lines[-100:]))
    else:
        st.info("Log file not available.")
