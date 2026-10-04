import streamlit as st
import requests
import uuid

def render_sidebar(api_base: str) -> dict:
    with st.sidebar:
        st.markdown("### 🔐 Authentication")
        
        # Logout logic
        if st.session_state.token and st.session_state.role:
            if st.session_state.role == "admin":
                st.markdown("""
                <div class="glass-card" style="padding: 1rem; border-left: 4px solid #a855f7;">
                    <p style="margin: 0; font-size: 0.9rem; color: #cbd5e1;">Logged in as:</p>
                    <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #f8fafc;">👑 {username}</p>
                    <span class="status-badge badge-purple" style="margin-top: 0.5rem;">Administrator</span>
                </div>
                """.format(username=st.session_state.username or 'Admin'), unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="glass-card" style="padding: 1rem; border-left: 4px solid #60a5fa;">
                    <p style="margin: 0; font-size: 0.9rem; color: #cbd5e1;">Logged in as:</p>
                    <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #f8fafc;">👤 {username}</p>
                    <span class="status-badge badge-blue" style="margin-top: 0.5rem;">User</span>
                </div>
                """.format(username=st.session_state.username or 'User'), unsafe_allow_html=True)
                
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.token = ""
                st.session_state.role = ""
                st.session_state.username = ""
                st.rerun()
        else:
            st.write("Login to access role-specific UI features.")
            username_input = st.text_input("Username", key="sb_user", placeholder="admin or user")
            password_input = st.text_input("Password", type="password", key="sb_pass", placeholder="••••••••")
            if st.button("🔑 Login", use_container_width=True, type="primary"):
                try:
                    response = requests.post(
                        f"{api_base}/auth/login",
                        data={"username": username_input, "password": password_input},
                    )
                    if response.ok:
                        data = response.json()
                        st.session_state.token = data.get("access_token", "")
                        st.session_state.role = data.get("role", "user")
                        st.session_state.username = username_input
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                except requests.RequestException as exc:
                    st.error(f"Login request failed: {exc}")
        
        st.divider()
        st.caption(f"🔗 Backend API: `{api_base}`")
        try:
            from requests.exceptions import RequestException
            r = requests.get(f"{api_base}/ready", timeout=3)
            if r.status_code == 200 and r.json().get("ready"):
                st.markdown('<span class="status-badge badge-green">🟢 System Online</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge badge-yellow">🟡 System Degraded</span>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<span class="status-badge" style="background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid #ef4444;">🔴 Backend Offline</span>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 💬 Recent Chats")
        if st.button("➕ New Support Topic", use_container_width=True, type="primary", key="new_chat_btn"):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

        headers_dict = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
        if not st.session_state.token:
            st.info("🔒 **Not logged in.** Please login above to access and resume your saved recent chat history.")
        else:
            if st.session_state.role == "admin":
                st.caption(f"Showing saved sessions for **👑 Admin ({st.session_state.username})**")
            else:
                st.caption(f"Showing saved sessions for **👤 {st.session_state.username}**")
                
            try:
                sessions_res = requests.get(f"{api_base}/api/v1/sessions", headers=headers_dict, timeout=10).json()
                sessions_list = sessions_res.get("sessions", [])
                if not sessions_list:
                    st.caption("No recent sessions found for your account.")
                else:
                    for s in sessions_list[:10]:
                        sid = s.get("session_id", "default")
                        preview = s.get("last_preview", sid[:8] + "...")
                        btn_label = f"💬 {preview}" if sid != st.session_state.get("session_id") else f"🟢 {preview}"
                        if st.button(btn_label, key=f"sess_{sid}", use_container_width=True):
                            st.session_state.session_id = sid
                            msg_res = requests.get(f"{api_base}/api/v1/sessions/{sid}/messages", headers=headers_dict, timeout=10).json()
                            st.session_state.messages = msg_res.get("messages", [])
                            st.rerun()
            except Exception:
                st.caption("Could not load sessions.")

    return {
        "token": st.session_state.token,
        "role": st.session_state.role,
        "session_id": st.session_state.session_id,
        "username": st.session_state.username
    }
