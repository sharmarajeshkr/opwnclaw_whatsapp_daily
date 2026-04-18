import builtins

def modify_app_py():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Inject Auth Logic right after Header
    header_marker = 'st.markdown(\'<p class="hero-sub">Manage WhatsApp delivery profiles and schedules for each user.</p>\', unsafe_allow_html=True)'
    
    auth_logic = """
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
"""
    content = content.replace(header_marker, header_marker + "\n" + auth_logic)

    # 2. Modify Tabs Generation
    old_tabs = """# ── Tabs ─────────────────────────────────────────────────────────────────────
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
    st.info("👋 Welcome! Please register and pair at least one WhatsApp account to unlock the full dashboard.")"""

    new_tabs = """# ── Tabs ─────────────────────────────────────────────────────────────────────
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
    ])"""
    content = content.replace(old_tabs, new_tabs)

    # 3. Fix With statements
    content = content.replace("with tab_profiles:", "if tab_profiles is not None:\n    with tab_profiles:")
    content = content.replace("if is_system_active:\n    with tab_config:", "if tab_config is not None:\n    with tab_config:")
    content = content.replace("if is_system_active:\n    with tab_performance:", "if tab_performance is not None:\n    with tab_performance:")
    content = content.replace("if is_system_active:\n    with tab_control:", "if tab_control is not None:\n    with tab_control:")
    content = content.replace("if is_system_active:\n    with tab_logs:", "if tab_logs is not None:\n    with tab_logs:")

    # 4. Modify tab_config inner logic
    old_config_start = """        all_users = ConfigManager.get_all_users()
        if not all_users:
            st.warning("Please register a user first.")
        else:
            selected_user = st.selectbox(
                "Select User to Configure",
                options=all_users,
                format_func=lambda x: f"+{x}",
            )

            config = ConfigManager.load_config(selected_user)"""

    new_config_start = """        if st.session_state.role == "ADMIN":
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
            
        config = ConfigManager.load_config(selected_user)"""
    content = content.replace(old_config_start, new_config_start)

    # Note: Because of indentation shifting, we need to correctly align new_config_start.
    # The simplest is to just use standard find & replace logic. Wait, Python text manipulation is brittle. Let's do it safely.
    
    # Let's fix the nested indentation in tab_config
    old_config_form = """            with st.form("user_config_form"):
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
                with col_s2:
                    sl_hook = st.text_input("Slack Webhook URL", value=config.channels.slack_webhook_url)
                with col_s3:
                    tg_token = st.text_input("Telegram Bot Token", value=config.channels.telegram_bot_token)

                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    tg_chat = st.text_input("Telegram Chat ID", value=config.channels.telegram_chat_id)"""

    new_config_form = """        with st.form("user_config_form"):
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
                pin = getattr(config, "pin_code", "0000")"""
    content = content.replace(old_config_form, new_config_form)

    old_config_save = """                if save_btn:
                    new_cfg = UserConfig(
                        schedule_time=schedule.strftime("%H:%M"),
                        timezone=tz_selection,
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
                    st.success(f"✅ Saved for +{selected_user}! Restart bot component to apply.")"""

    new_config_save = """            if save_btn:
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
                st.success(f"✅ Saved for +{selected_user}! Setting changes apply immediately via hot-reload.")"""
    content = content.replace(old_config_save, new_config_save)

    # Dedent the rest of the config form (lines from st.markdown("---") to save_btn = )
    old_topics_section = """                st.markdown("---")
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
                    save_btn = st.form_submit_button("💾 Save User Configuration", type="primary", use_container_width=True)"""

    new_topics_section = """            st.markdown("---")
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
                save_btn = st.form_submit_button("💾 Save Configuration", type="primary", use_container_width=True)"""
    content = content.replace(old_topics_section, new_topics_section)

    # 5. Fix tab_performance
    old_perf_start = """        all_users = ConfigManager.get_all_users()
        if not all_users:
            st.warning("Please register a user first.")
        else:
            selected_perf_user = st.selectbox(
                "Select User to View Performance",
                options=all_users,
                format_func=lambda x: f"+{x}",
                key="perf_user_select"
            )
            
            perf_data = PerformanceTracker.get_all_time_summary(selected_perf_user)"""

    new_perf_start = """        if st.session_state.role == "ADMIN":
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
            
        perf_data = PerformanceTracker.get_all_time_summary(selected_perf_user)"""
    content = content.replace(old_perf_start, new_perf_start)

    # Fix indentation for the rest of tab_performance.
    old_perf_rest = """            if not perf_data:
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
                )"""

    new_perf_rest = """        if not perf_data:
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
            )"""
    content = content.replace(old_perf_rest, new_perf_rest)

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    modify_app_py()
    print("Done")
