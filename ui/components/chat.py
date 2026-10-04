import streamlit as st
import requests
import time

def render_chat(api_base: str, headers: dict, session_id: str):
    col_stop, col_info = st.columns([1, 4])
    with col_stop:
        if st.button("🛑 Stop Generation", key="term_btn_top", use_container_width=True):
            if sid := session_id:
                try:
                    requests.post(f"{api_base}/api/v1/sessions/{sid}/terminate", json={}, headers=headers, timeout=10)
                    st.toast("🛑 Sent termination signal to active generation!")
                except Exception:
                    pass
    with col_info:
        st.caption("💡 Tip: Click **🛑 Stop Generation** anytime during text output to immediately terminate an ongoing chat response.")

    st.divider()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                conf = message.get("confidence")
                sources = message.get("sources")
                if conf is not None or sources:
                    cols = st.columns([1, 4])
                    with cols[0]:
                        if conf is not None:
                            badge_class = "badge-green" if conf >= 0.8 else ("badge-yellow" if conf >= 0.5 else "badge-purple")
                            st.markdown(f'<span class="status-badge {badge_class}">🎯 Conf: {conf*100:.0f}%</span>', unsafe_allow_html=True)
                    with cols[1]:
                        if sources:
                            with st.expander(f"📚 Cited Sources ({len(sources)} documents referenced)"):
                                for idx, src in enumerate(sources, 1):
                                    src_name = src.get("source", src.get("doc_id", "Unknown Document"))
                                    score = src.get("relevance_score", src.get("similarity_score", 0.0))
                                    st.markdown(f"**{idx}. {src_name}** `(Relevance Score: {score:.2f})`")
                                    if snippet := src.get("content_snippet"):
                                        st.caption(f'"{snippet[:200]}..."')

    if user_query := st.chat_input("Ask a support question..."):
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})

        with st.chat_message("assistant"):
            try:
                response = requests.post(
                    f"{api_base}/chat/stream",
                    json={"query": user_query, "chat_history": st.session_state.messages[:-1], "session_id": session_id},
                    headers=headers,
                    stream=True,
                    timeout=120,
                )
                response.raise_for_status()
                
                placeholder = st.empty()
                full_answer = ""
                for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                    if chunk:
                        full_answer += chunk
                        if "[CANCELLED:" in full_answer or "[CANCEL:" in full_answer:
                            full_answer = "🚨 **[CANCELLED: This response violated safety guidelines and has been retracted.]**"
                            placeholder.markdown(full_answer)
                            break
                        placeholder.markdown(full_answer + "▌")
                placeholder.markdown(full_answer)
                
                # Append locally immediately so output ALWAYS displays on screen
                new_msg = {"role": "assistant", "content": full_answer}
                st.session_state.messages.append(new_msg)
                
                # Fetch updated session messages from backend ONLY if backend has more or equal messages (preventing erasure)
                time.sleep(0.35)
                if session_id:
                    try:
                        res_msgs = requests.get(f"{api_base}/api/v1/sessions/{session_id}/messages", headers=headers, timeout=10).json()
                        if res_msgs and (msgs := res_msgs.get("messages")) and len(msgs) >= len(st.session_state.messages):
                            st.session_state.messages = msgs
                    except Exception:
                        pass
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Chat request failed: {exc}")
