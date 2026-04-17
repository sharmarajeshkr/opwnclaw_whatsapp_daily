import streamlit as st
import subprocess
import datetime
import os
import json
import time
import pytz
import pandas as pd
from src.core.config import ConfigManager, UserConfig
from src.core.performance import PerformanceTracker
from src.core.logger import get_logger
from src.core.utils import (
    is_bot_running,
    start_bot,
    stop_bot,
    delete_user_data,
    is_user_paired,
    trigger_qr_script,
)

logger = get_logger("StreamlitApp")

# ── Helpers imported from src.core.utils ─────────────────────────────────────
# is_bot_running, start_bot, stop_bot, delete_user_data,
# is_user_paired, trigger_qr_script are all imported at the top.


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

# ── Authentication Gate ──────────────────────────────────────────────────────
from src.core.env import get_admin_password

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if not st.session_state.authenticated:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🔒 Dashboard Login")
    login_phone = st.text_input("Phone Number (Leave blank for Admin)", placeholder="e.g. 919876543210")
    login_pass = st.text_input("Password / PIN", type="password")
    
    if st.button("Login", type="primary"):
        admin_pass = get_admin_password()
        
        if not login_phone.strip():
            if admin_pass and login_pass == admin_pass:
                st.session_state.authenticated = True
                st.session_state.role = "ADMIN"
                st.rerun()
            else:
                st.error("Invalid Admin password.")
        else:
            phone_clean = login_phone.strip().lstrip("+")
            users = ConfigManager.get_all_users()
            if phone_clean in users:
                cfg = ConfigManager.load_config(phone_clean)
                if login_pass == getattr(cfg, "pin_code", "0000"):
                    st.session_state.authenticated = True
                    st.session_state.role = "USER"
                    st.session_state.auth_user = phone_clean
                    st.rerun()
                else:
                    st.error("Invalid PIN.")
            else:
                st.error("Phone number not registered.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

st.sidebar.markdown(f"**Logged in as:** {st.session_state.role}")
if st.session_state.role == "USER":
    st.sidebar.markdown(f"**Profile:** +{st.session_state.auth_user}")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.role = None
    st.session_state.auth_user = None
    st.rerun()


# ── Global Pairing Check ─────────────────────────────────────────────────────
paired_users = [u for u in ConfigManager.get_all_users() if is_user_paired(u)]
is_system_active = len(paired_users) > 0

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_profiles = tab_config = tab_performance = tab_control = tab_logs = None

if st.session_state.role == "ADMIN":
    if is_system_active:
        tab_profiles, tab_config, tab_performance, tab_control, tab_logs = st.tabs([
            "👥 User Profiles",
            "⚙️ Configure User",
            "📊 Performance Dashboard",
            "🚀 System Control",
            "📜 Logs",
        ])
    else:
        tab_profiles, = st.tabs(["👥 User Registration & Pairing"])
        st.info("👋 Welcome! Please register and pair at least one WhatsApp account to unlock the full dashboard.")
elif st.session_state.role == "USER":
    tab_config, tab_performance = st.tabs([
        "⚙️ My Configuration",
        "📊 My Performance",
    ])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — USER PROFILES
# ────────────────────────────────────────────────────────────────────────────
if tab_profiles is not None:
    with tab_profiles:
        st.subheader("Registered Users Overview")

        users = ConfigManager.get_all_users()

        if users:
            # ── Table Header ──
            h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([2, 1.5, 1.5, 3, 2.5])
            h_col1.markdown("**📱 Phone number**")
            h_col2.markdown("**Status**")
            h_col3.markdown("**Schedule**")
            h_col4.markdown("**Topics**")
            h_col5.markdown("**Actions**")
            st.markdown("<hr style='margin-top:0.2rem; margin-bottom:0.8rem;'/>", unsafe_allow_html=True)

            # ── Table Rows ──
            for phone in users:
                cfg = ConfigManager.load_config(phone)
                qr_path = os.path.join("data", f"qr_{phone}.png")
                paired = not os.path.exists(qr_path)
                running = is_bot_running(phone)
            
                sched = cfg.schedule_time if cfg.schedule_time else "—"
                active_topics = [v for k, v in cfg.topics.model_dump().items() if v]
                topic_str = ", ".join(active_topics) if active_topics else "None"

                c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 3, 2.5])
            
                c1.markdown(f"+{phone}")
            
                if running:
                    c2.markdown('<span class="badge-active">● Running</span>', unsafe_allow_html=True)
                elif paired:
                    c2.markdown('<span class="badge-pending" style="color:rgb(168 85 247); border-color:rgba(168,85,247,0.4);">○ Stopped</span>', unsafe_allow_html=True)
                else:
                    c2.markdown('<span class="badge-pending">◌ Scan QR</span>', unsafe_allow_html=True)
                
                c3.markdown(sched)
                c4.markdown(f"<span style='font-size:0.85rem;'>{topic_str}</span>", unsafe_allow_html=True)
            
                with c5:
                    # Actions within horizontal flex
                    a1, a2, a3 = st.columns([1,1,1])
                    with a1:
                        if not running and paired:
                            if st.button("▶️", key=f"start_{phone}", help="Start"):
                                start_bot(phone)
                                st.rerun()
                        elif not paired:
                            if st.button("🔄 QR", key=f"qr_{phone}", help="Trigger QR"):
                                trigger_qr_script(phone)
                                st.rerun()
                    with a2:
                        if running:
                            if st.button("⏹️", key=f"stop_{phone}", help="Stop"):
                                stop_bot(phone)
                                st.rerun()
                    with a3:
                        if st.button("🗑️", key=f"del_{phone}", help="Delete User"):
                            delete_user_data(phone)
                            st.rerun()

                st.markdown("<hr style='margin-top:0.4rem; margin-bottom:0.4rem; opacity:0.3;'/>", unsafe_allow_html=True)

        else:
            st.info("No users registered yet.")

        st.markdown("<br>", unsafe_allow_html=True)

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
                elif raw in users and is_user_paired(raw):
                    st.warning(f"+{raw} is already registered and paired.")
                else:
                    trigger_qr_script(raw)
                    st.success(f"✅ Initializing registration for +{raw}. QR will appear shortly.")
                    time.sleep(3)
                    st.rerun()

        # QR Display
        pending_qr_users = [
            u for u in ConfigManager.get_all_users()
            if not is_user_paired(u)
        ]
        if pending_qr_users:
            st.subheader("📷 Pending Pairing — Scan QR Code")
            for u in pending_qr_users:
                qr_path = os.path.join("data", f"qr_{u}.png")
                st.markdown(f"**+{u}** — Scan in WhatsApp → Linked Devices")
            
                if os.path.exists(qr_path):
                    st.image(qr_path, caption=f"QR for +{u}", width=280)
                else:
                    st.warning(f"⏳ QR for +{u} is being initialized or ready. If stuck, hit the refresh button below.")
            
                col_ref, col_space = st.columns([1, 1])
                with col_ref:
                    if st.button(f"🔄 Refresh +{u}", key=f"r_{u}"):
                        st.rerun()

# ────────────────────────────────────────────────────────────────────────────
    # TAB 2 — CONFIGURE USER
# ────────────────────────────────────────────────────────────────────────────
if tab_config is not None:
    with tab_config:
            st.subheader("⚙️ Per-User Configuration")

            if st.session_state.role == "ADMIN":
                all_users = ConfigManager.get_all_users()
                if not all_users:
                    st.warning("Please register a user first.")
                    st.stop()
                selected_user = st.selectbox(
                    "Select User to Configure",
                    options=all_users,
                    format_func=lambda x: f"+{x}",
                )
            else:
                selected_user = st.session_state.auth_user
                st.markdown(f"**Editing Profile:** +{selected_user}")
            
            config = ConfigManager.load_config(selected_user)

            with st.form("user_config_form"):
                col_s1, col_s1a, col_s2, col_s3 = st.columns([1, 1, 1, 1])
                with col_s1:
                    t_hour, t_min = map(int, config.schedule_time.split(":"))
                    schedule = st.time_input("Daily Delivery Time", value=datetime.time(t_hour, t_min))
                with col_s1a:
                    tz_idx = 0
                    common_tzs = pytz.common_timezones
                    if config.timezone in common_tzs:
                        tz_idx = common_tzs.index(config.timezone)
                    tz_selection = st.selectbox("Timezone", options=common_tzs, index=tz_idx)
            
                if st.session_state.role == "ADMIN":
                    with col_s2:
                        sl_hook = st.text_input("Slack Webhook URL", value=config.channels.slack_webhook_url)
                    with col_s3:
                        tg_token = st.text_input("Telegram Bot Token", value=config.channels.telegram_bot_token)
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        tg_chat = st.text_input("Telegram Chat ID", value=config.channels.telegram_chat_id)
                    with col_t2:
                        pin = st.text_input("User PIN Code", value=getattr(config, "pin_code", "0000"))
                else:
                    sl_hook = config.channels.slack_webhook_url
                    tg_token = config.channels.telegram_bot_token
                    tg_chat = config.channels.telegram_chat_id
                    pin = getattr(config, "pin_code", "0000")

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
                    save_btn = st.form_submit_button("💾 Save Configuration", type="primary", use_container_width=True)

                if save_btn:
                    new_cfg = UserConfig(
                        schedule_time=schedule.strftime("%H:%M"),
                        timezone=tz_selection,
                        pin_code=pin,
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
                    st.success(f"✅ Saved for +{selected_user}! Setting changes apply immediately via hot-reload.")

# ────────────────────────────────────────────────────────────────────────────
    # TAB 3 — PERFORMANCE DASHBOARD
# ────────────────────────────────────────────────────────────────────────────
if tab_performance is not None:
    with tab_performance:
            st.subheader("📊 User Performance Dashboard")
        
            if st.session_state.role == "ADMIN":
                all_users = ConfigManager.get_all_users()
                if not all_users:
                    st.warning("Please register a user first.")
                    st.stop()
                selected_perf_user = st.selectbox(
                    "Select User to View Performance",
                    options=all_users,
                    format_func=lambda x: f"+{x}",
                    key="perf_user_select"
                )
            else:
                selected_perf_user = st.session_state.auth_user
            
            perf_data = PerformanceTracker.get_all_time_summary(selected_perf_user)
            
            if not perf_data:
                st.info(f"No performance data recorded yet for +{selected_perf_user}. Complete an interview session first!")
            else:
                df = pd.DataFrame(perf_data)
            
                # Display high-level metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                total_attempts = df["attempts"].sum()
                avg_overall = df["avg_score"].mean()
                top_topic = df.loc[df["avg_score"].idxmax()]["topic"]
                weakest_topic = df.loc[df["avg_score"].idxmin()]["topic"]
            
                with col_m1:
                    st.metric("Total Answers", int(total_attempts))
                with col_m2:
                    st.metric("Overall Average Score", f"{avg_overall:.1f} / 10")
                with col_m3:
                    st.metric("Strongest Topic", top_topic)
            
                st.markdown("---")
                st.markdown("### Average Score by Topic")
            
                # Bar chart for average scores
                chart_data = df.set_index("topic")[["avg_score"]]
                # Make sure y-axis max is 10 for scores
                st.bar_chart(chart_data, height=400, y_label="Average Score (Out of 10)")
            
                # Data table
                st.markdown("### Detailed Breakdown")
                st.dataframe(
                    df.rename(columns={
                        "topic": "Topic", 
                        "avg_score": "Average Score", 
                        "attempts": "Total Attempts", 
                        "min_score": "Min Score", 
                        "max_score": "Max Score"
                    }), 
                    use_container_width=True
                )

# ────────────────────────────────────────────────────────────────────────────
    # TAB 4 — SYSTEM CONTROL
# ────────────────────────────────────────────────────────────────────────────
if tab_control is not None:
    with tab_control:
            st.subheader("🚀 Bulk Orchestration")
            st.markdown("Start or stop bots for all registered users at once.")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Start ALL Active Bots", use_container_width=True):
                    from src.core.utils import start_all_bots
                    start_all_bots()
                    st.success("✅ All bots triggered.")
            with col2:
                if st.button("🛑 Stop ALL Active Bots", use_container_width=True):
                    from src.core.utils import stop_all_bots
                    stop_all_bots()
                    st.warning("⏺️ Terminated all bot processes.")

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
    # TAB 5 — LOGS
# ────────────────────────────────────────────────────────────────────────────
if tab_logs is not None:
    with tab_logs:
            st.subheader("📜 System Logs")
            if st.button("Refresh Log", key="refresh_btn"):
                pass

            log_path = os.path.join("data", "bot.log")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                st.code("".join(lines[-100:]))
            else:
                st.info("Log file not available.")
