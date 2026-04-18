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
from src.core.db import init_db

logger = get_logger("StreamlitApp")

# Initialize database schema
init_db()

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
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');

html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }

/* Hide the sidebar collapse/expand arrow button and any orphan icon text */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[data-testid="collapsedControl"],
section[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
}

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

# ── Hide sidebar collapse arrow (JS targets the Streamlit host frame) ─────────
import streamlit.components.v1 as _components
_components.html("""
<script>
(function hideSidebarArrow() {
    function remove() {
        var selectors = [
            '[data-testid="collapsedControl"]',
            '[data-testid="stSidebarCollapsedControl"]'
        ];
        selectors.forEach(function(sel) {
            var els = window.parent.document.querySelectorAll(sel);
            els.forEach(function(el) {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.width = '0';
                el.style.overflow = 'hidden';
            });
        });
    }
    // Run immediately and again after Streamlit re-renders
    remove();
    setTimeout(remove, 500);
    setTimeout(remove, 1500);
})();
</script>
""", height=0)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown('<p class="hero-title">🦀 Innterview Bot Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">Manage WhatsApp delivery profiles and schedules for each user.</p>', unsafe_allow_html=True)

# ── Authentication Gate ──────────────────────────────────────────────────────
from src.core.sys_config import settings

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if not st.session_state.authenticated:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    tab_login, tab_register = st.tabs(["🔒 Login", "➕ Register New User"])
    
    with tab_login:
        st.subheader("Welcome Back")
        login_phone = st.text_input("Phone Number (Leave blank for Admin)", placeholder="e.g. 919876543210")
        login_pass = st.text_input("Password / PIN", type="password")
        
        if st.button("Login", type="primary", use_container_width=True):
            admin_pass = settings.ADMIN_PASSWORD
            
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
                    
    with tab_register:
        st.subheader("Join OpenClaw")
        reg_phone = st.text_input("Your Mobile Number (with country code)", placeholder="e.g. +919876543210")
        reg_pin = st.text_input("Set a 4-Digit PIN", type="password", max_chars=4)
        
        if st.button("Create Account", type="primary", use_container_width=True):
            phone_clean = reg_phone.strip().lstrip("+")
            if not phone_clean.isdigit():
                st.error("Please enter a valid phone number with country code.")
            elif not reg_pin:
                st.error("Please set a PIN.")
            elif phone_clean in ConfigManager.get_all_users():
                st.warning("This phone number is already registered! Please login.")
            else:
                # Create default config for the new user
                from src.core.config import UserConfig, ChannelsConfig
                default_channels = ChannelsConfig(whatsapp_target=phone_clean)
                new_cfg = UserConfig(channels=default_channels, pin_code=reg_pin)
                ConfigManager.save_config(phone_clean, new_cfg)
                st.success(f"Account for +{phone_clean} created successfully! You can now login.")
                
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


# ── Early Pairing Gate for USER ──────────────────────────────────────────────
# If a USER just registered but hasn't scanned QR yet, show the pairing screen
# as the ONLY thing on the page — no other tabs until they are paired.
if st.session_state.role == "USER":
    user_phone = st.session_state.auth_user
    if not is_user_paired(user_phone):
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<p class="hero-title" style="font-size:1.4rem;">📱 Pair Your WhatsApp</p>', unsafe_allow_html=True)
        st.markdown("Before we can send you interview content, you need to link your WhatsApp account by scanning a QR code.")
        st.markdown("---")

        qr_path = os.path.join("data", f"qr_{user_phone}.png")

        if os.path.exists(qr_path):
            st.success("✅ QR Code is ready! Open WhatsApp → **Linked Devices** → **Link a Device** and scan below.")
            st.image(qr_path, caption=f"QR for +{user_phone}", width=300)
            if st.button("🔄 I've scanned it — check status", use_container_width=True):
                st.rerun()
        else:
            st.info("Click the button below to generate your personal QR code.")
            if st.button("🔲 Generate My QR Code", type="primary", use_container_width=True):
                trigger_qr_script(user_phone)
                import time
                time.sleep(3)
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    else:
        # User IS paired — make sure their bot is running
        if not is_bot_running(user_phone):
            start_bot(user_phone)


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_profiles = tab_config = tab_performance = tab_control = tab_logs = None

# Global pairing check (for ADMIN system status)
paired_users = [u for u in ConfigManager.get_all_users() if is_user_paired(u)]
is_system_active = len(paired_users) > 0

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
                # Use DB-driven status
                paired = is_user_paired(phone)
                running = is_bot_running(phone)
                cfg = ConfigManager.load_config(phone)
            
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
            col_ph, col_pin, col_btn = st.columns([3, 1, 1])
            with col_ph:
                new_phone = st.text_input(
                    "Mobile Number (with country code)",
                    placeholder="+919876543210",
                    label_visibility="collapsed",
                )
            with col_pin:
                new_pin = st.text_input(
                    "PIN",
                    placeholder="PIN (4 digits)",
                    label_visibility="collapsed",
                    max_chars=4,
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
                    from src.core.config import UserConfig, ChannelsConfig
                    default_channels = ChannelsConfig(whatsapp_target=raw)
                    pin_value = new_pin.strip() if new_pin.strip() else "0000"
                    new_cfg = UserConfig(channels=default_channels, pin_code=pin_value)
                    ConfigManager.save_config(raw, new_cfg)
                    trigger_qr_script(raw)
                    st.success(f"✅ User +{raw} registered (PIN: {pin_value}). QR will appear shortly.")
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
                
                st.markdown("---")
                st.subheader("📱 WhatsApp Pairing & Status")
                
                qr_path = os.path.join("data", f"qr_{selected_user}.png")
                paired = not os.path.exists(qr_path)
                running = is_bot_running(selected_user)
                
                c_stat, c_act1, c_act2 = st.columns([2, 1, 1])
                with c_stat:
                    if running:
                        st.markdown('<span class="badge-active">● Running</span>', unsafe_allow_html=True)
                    elif paired:
                        st.markdown('<span class="badge-pending" style="color:rgb(168 85 247); border-color:rgba(168,85,247,0.4);">○ Stopped</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="badge-pending">◌ Scan QR</span>', unsafe_allow_html=True)
                
                with c_act1:
                    if not running and paired:
                        if st.button("▶️ Start Engine", key=f"user_start_{selected_user}", use_container_width=True):
                            start_bot(selected_user)
                            st.rerun()
                    elif not paired:
                        if st.button("🔄 Generate QR", key=f"user_qr_{selected_user}", use_container_width=True):
                            trigger_qr_script(selected_user)
                            st.rerun()
                with c_act2:
                    if running:
                        if st.button("⏹️ Stop Engine", key=f"user_stop_{selected_user}", use_container_width=True):
                            stop_bot(selected_user)
                            st.rerun()
                            
                if not paired:
                    st.info("To pair your WhatsApp, click 'Generate QR'. Once it appears, scan it using WhatsApp > Linked Devices.")
                    if os.path.exists(qr_path):
                        st.image(qr_path, caption=f"QR Code for +{selected_user}", width=300)
                    else:
                        st.warning("QR is initializing or not requested. Wait a few seconds and page your refresh.")
                st.markdown("---")
            
            config = ConfigManager.load_config(selected_user)

            with st.form("user_config_form"):
                col_s1, col_s1a, col_s2, col_s3 = st.columns([1, 1, 1, 1])
                with col_s1:
                    schedule = st.text_input(
                        "Default Delivery Time (HH:MM)",
                        value=config.schedule_time,
                        placeholder="e.g. 20:00",
                        help="Fallback time for any topic that has no individual time set."
                    )
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
                st.subheader("📚 Topic Schedule")

                # Detect if any topic currently has an individual time set → default to Per-Topic
                has_per_topic = any(
                    getattr(config.topics, f"topic_{n}_time", "").strip()
                    for n in range(1, 6)
                )
                schedule_mode = st.radio(
                    "Schedule Mode",
                    options=["🌐 Global — one time for all topics", "🕐 Per-Topic — different time per topic"],
                    index=1 if has_per_topic else 0,
                    horizontal=True,
                    help="Global: all topics fire at the same time. Per-Topic: each topic has its own delivery time.",
                )
                is_per_topic = schedule_mode.startswith("🕐")

                if is_per_topic:
                    st.caption("Set a custom delivery time per topic. Leave blank to fall back to the Default Time above.")
                else:
                    st.caption(f"All topics will be delivered as one batch at the Default Delivery Time above.")

                # Table header — hide time column in Global mode
                if is_per_topic:
                    th_topic, th_label, th_time = st.columns([2, 3, 1])
                    th_topic.markdown("**Topic**")
                    th_label.markdown("**Subject / Label**")
                    th_time.markdown("**Time (HH:MM)**")
                else:
                    th_topic, th_label = st.columns([2, 3])
                    th_topic.markdown("**Topic**")
                    th_label.markdown("**Subject / Label**")

                TOPIC_DEFS = [
                    ("1", "🏗️ Architecture Challenge"),
                    ("2", "🔬 Deep Dive 1"),
                    ("3", "🔬 Deep Dive 2"),
                    ("4", "📰 Fresh Updates"),
                    ("5", "📖 Medium Articles"),
                ]
                topic_values = {}
                for n, label in TOPIC_DEFS:
                    if is_per_topic:
                        c_topic, c_label, c_time = st.columns([2, 3, 1])
                    else:
                        c_topic, c_label = st.columns([2, 3])
                    with c_topic:
                        st.markdown(f"{label}")
                    with c_label:
                        topic_values[f"t{n}"] = st.text_input(
                            f"topic_{n}_label",
                            value=getattr(config.topics, f"topic_{n}"),
                            label_visibility="collapsed",
                            key=f"topic_{n}_label_{selected_user}"
                        )
                    if is_per_topic:
                        with c_time:
                            topic_values[f"t{n}_time"] = st.text_input(
                                f"topic_{n}_time",
                                value=getattr(config.topics, f"topic_{n}_time", ""),
                                placeholder="HH:MM",
                                label_visibility="collapsed",
                                key=f"topic_{n}_time_{selected_user}",
                                help=f"Leave blank to use Default Time ({config.schedule_time})"
                            )
                    else:
                        # Global mode — clear all per-topic times on save
                        topic_values[f"t{n}_time"] = ""

                st.markdown("<br>", unsafe_allow_html=True)
                save_btn = st.form_submit_button("💾 Save Configuration", type="primary", use_container_width=True)

                if save_btn:
                    # Validate custom times
                    time_error = False
                    for n, _ in TOPIC_DEFS:
                        t = topic_values[f"t{n}_time"].strip()
                        if t:
                            parts = t.split(":")
                            valid = (
                                len(parts) == 2
                                and parts[0].isdigit() and parts[1].isdigit()
                                and 0 <= int(parts[0]) <= 23
                                and 0 <= int(parts[1]) <= 59
                            )
                            if not valid:
                                st.error(f"Invalid time for topic {n}: '{t}'. Use HH:MM format (e.g. 08:30).")
                                time_error = True
                    # Validate global time
                    global_t = schedule.strip()
                    g_parts = global_t.split(":")
                    if not (len(g_parts) == 2 and g_parts[0].isdigit() and g_parts[1].isdigit()):
                        st.error("Default Delivery Time must be in HH:MM format.")
                        time_error = True

                    if not time_error:
                        new_cfg = UserConfig(
                            schedule_time=global_t,
                            timezone=tz_selection,
                            pin_code=pin,
                            topics={
                                "topic_1": topic_values["t1"], "topic_1_time": topic_values["t1_time"],
                                "topic_2": topic_values["t2"], "topic_2_time": topic_values["t2_time"],
                                "topic_3": topic_values["t3"], "topic_3_time": topic_values["t3_time"],
                                "topic_4": topic_values["t4"], "topic_4_time": topic_values["t4_time"],
                                "topic_5": topic_values["t5"], "topic_5_time": topic_values["t5_time"],
                            },
                            channels={
                                "whatsapp_target": selected_user,
                                "telegram_bot_token": tg_token,
                                "telegram_chat_id": tg_chat,
                                "slack_webhook_url": sl_hook,
                            }
                        )
                        ConfigManager.save_config(selected_user, new_cfg)
                        st.success(f"✅ Saved! Topic schedules apply within 60 seconds via hot-reload.")

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
                        "Status": "Ready" if is_user_paired(u) else "Awaiting Pair"
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
