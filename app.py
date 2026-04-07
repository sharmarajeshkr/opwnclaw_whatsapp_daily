import streamlit as st
import subprocess
import datetime
from src.config_manager import ConfigManager

st.set_page_config(page_title="OpenClaw Bot Configurator", page_icon="🦀", layout="wide")

st.title("🦀 Articles/Interview Delivery System")

# Load existing configuration
config = ConfigManager.load_config()

tab1, tab2 = st.tabs(["⚙️ Configuration", "📜 System Logs"])

with tab1:
    # ---- BOT CONTROL ----
    st.subheader("⚙️ System Control")
    st.markdown("Manage the backend daemon running the WhatsApp integration and scheduler.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Start Bot Process"):
            # Launching asynchronously and detaching
            subprocess.Popen(["powershell", "-Command", "Start-Process -NoNewWindow .\\venv\\Scripts\\python.exe main.py"])
            st.success("✅ Backend bot daemon triggered!")

    with col2:
        if st.button("🛑 Stop Active Bots"):
            # This is a broad kill switch.
            st.warning("Sending terminate signal down... Ensure you reload Streamlit if it hangs.")
            subprocess.run('powershell -Command "Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match \'main.py\' } | Stop-Process -Force"', shell=True)

    st.divider()

    # ---- CONFIGURATION FORMS ----
    with st.form("config_form"):
        st.subheader("⏱️ Delivery Schedule & Channels")
        
        col_s1, col_s2, col_s3 = st.columns([1, 1, 1])
        with col_s1:
            t_hour, t_min = map(int, config.get("schedule_time", "06:00").split(":"))
            schedule = st.time_input("Daily Delivery Time", value=datetime.time(t_hour, t_min))
        with col_s2:
            w_target = st.text_input("WhatsApp Target", value=config["channels"].get("whatsapp_target", "+919789824976"))
        with col_s3:
            sl_hook = st.text_input("Slack Webhook URL", value=config["channels"].get("slack_webhook_url", ""))

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tg_token = st.text_input("Telegram Bot Token", value=config["channels"].get("telegram_bot_token", ""))
        with col_t2:
            tg_chat = st.text_input("Telegram Chat ID", value=config["channels"].get("telegram_chat_id", ""))

        st.subheader("📚 5-Part Content Sequence")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            t1 = st.text_input("1. Architecture Challenge", value=config["topics"].get("topic_1", "Architecture Challenge"))
            t2 = st.text_input("2. Deep Dive Subject 1", value=config["topics"].get("topic_2", "Kafka"))
            t3 = st.text_input("3. Deep Dive Subject 2", value=config["topics"].get("topic_3", "Agentic AI"))
        with col_c2:
            t4 = st.text_input("4. Fresh Updates 1", value=config["topics"].get("topic_4", "AI News"))
            t5 = st.text_input("5. Fresh Updates 2", value=config["topics"].get("topic_5", "Latest Global News"))
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("💾 Save Configuration", type="primary", use_container_width=True)

        if submitted:
            config["schedule_time"] = schedule.strftime("%H:%M")
            config["topics"] = {
                "topic_1": t1,
                "topic_2": t2,
                "topic_3": t3,
                "topic_4": t4,
                "topic_5": t5
            }
            config["channels"] = {
                "whatsapp_target": w_target,
                "telegram_bot_token": tg_token,
                "telegram_chat_id": tg_chat,
                "slack_webhook_url": sl_hook
            }
            ConfigManager.save_config(config)
            st.success("✅ Configuration saved! Please press 'Stop Active Bots' and then 'Start Bot Process' above to apply changes.")

with tab2:
    st.subheader("📜 Live System Logs")
    st.markdown("Real-time output from the `main.py` daemon.")
    
    col_ref, _ = st.columns([1, 4])
    with col_ref:
        if st.button("🔄 Refresh Logs"):
            pass # Reruns streamlit automatically
            
    import os
    log_path = os.path.join("data", "bot.log")
    
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Show last 100 lines
            log_content = "".join(lines[-100:])
            st.code(log_content, language="log")
    else:
        st.info("No logs generated yet. Make sure the bot is running!")
