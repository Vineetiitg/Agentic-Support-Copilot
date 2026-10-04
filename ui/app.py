import os
from pathlib import Path
import streamlit as st
import uuid
import requests

from components.sidebar import render_sidebar
from components.chat import render_chat
from components.admin import render_admin, render_documents_tab

st.set_page_config(page_title="Support Docs Copilot", page_icon="🚀", layout="wide")

def load_css():
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

load_css()

st.markdown("""
<div style="padding: 0.5rem 0; margin-bottom: 1rem;">
    <h1 style="font-size: 2.6rem; margin: 0;">🚀 Support Docs Copilot</h1>
    <p style="color: #94a3b8; font-size: 1.05rem; margin-top: 0.2rem;">
        Next-Gen Agentic RAG Assistant powered by LangGraph, Speculative Retrieval & Cohere Reranking
    </p>
</div>
""", unsafe_allow_html=True)

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "token" not in st.session_state:
    st.session_state.token = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "username" not in st.session_state:
    st.session_state.username = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

sidebar_state = render_sidebar(BACKEND_BASE_URL)

headers = {"Authorization": f"Bearer {sidebar_state['token']}"} if sidebar_state['token'] else {}

if sidebar_state["role"] == "admin":
    chat_tab, docs_tab, admin_tab = st.tabs(["💬 Chat Copilot", "📚 Documents", "👑 Admin / Analytics"])
    with chat_tab:
        render_chat(BACKEND_BASE_URL, headers, sidebar_state["session_id"])
    with docs_tab:
        render_documents_tab(BACKEND_BASE_URL, headers)
    with admin_tab:
        render_admin(BACKEND_BASE_URL, headers)
else:
    chat_tab, docs_tab, status_tab = st.tabs(["💬 Chat Copilot", "📚 Documents", "⚙️ System Status"])
    with chat_tab:
        render_chat(BACKEND_BASE_URL, headers, sidebar_state["session_id"])
    with docs_tab:
        render_documents_tab(BACKEND_BASE_URL, headers)
    with status_tab:
        st.markdown("### ⚙️ System Status")
        try:
            r = requests.get(f"{BACKEND_BASE_URL}/ready", timeout=5)
            ready_data = r.json() if r.ok else {}
            cols = st.columns(3)
            with cols[0]:
                st.metric("Overall Status", "🟢 Ready" if ready_data.get("ready") else "🟡 Degraded")
            with cols[1]:
                st.metric("Vector Store", "🟢 Online" if ready_data.get("vector_store") else "🔴 Offline")
            with cols[2]:
                st.metric("LLM Provider", "🟢 Connected" if ready_data.get("llm") else "🔴 Offline")
            st.json(ready_data)
        except Exception as exc:
            st.error(f"Readiness check failed: {exc}")
        st.divider()
        st.info("💡 **Admin Notice**: To access Document Ingestion, RAGAS Benchmarks, and LangSmith Observability tools, please login as an Administrator.")
