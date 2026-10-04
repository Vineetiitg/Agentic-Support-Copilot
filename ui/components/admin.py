import streamlit as st
import requests
import time
import os

DATA_DIR = os.getenv("DATA_DIR", "data/docs")

def get_json(api_base, path, headers):
    r = requests.get(f"{api_base}{path}", headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def post_json(api_base, path, headers, payload=None):
    with st.spinner("Processing..."):
        r = requests.post(f"{api_base}{path}", headers=headers, json=payload or {}, timeout=300)
    r.raise_for_status()
    return r.json()

def poll_job_status(api_base, headers, job_id: str, status_text: str = "Processing in background..."):
    with st.status(status_text, expanded=True) as status:
        st.write("Job enqueued in Redis worker queue...")
        status_placeholder = st.empty()
        for _ in range(120):
            try:
                res = get_json(api_base, f"/tasks/status/{job_id}", headers)
                job_status = res.get("status", "unknown")
                status_placeholder.markdown(f"Status: **{job_status}** ⏳")
                if err_msg := res.get("error"):
                    st.error(f"Error details: {err_msg}")
                if job_status in ("complete", "success"):
                    status_placeholder.markdown("Status: **Complete** ✅")
                    status.update(label="Job Completed Successfully!", state="complete", expanded=False)
                    return res.get("result")
                elif job_status in ("not_found", "error", "failed", "error_try_again"):
                    status_placeholder.markdown(f"Status: **{job_status}** ❌")
                    status.update(label=f"Job Finished ({job_status})", state="complete" if job_status == "complete" else "error", expanded=True)
                    return res.get("result")
            except requests.RequestException as e:
                st.error(f"⚠️ Connection error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
            time.sleep(1.5)
        status.update(label="Job Timed Out / Still Running", state="error")
    return None

def render_documents_tab(api_base: str, headers: dict):
    st.markdown("### 📚 Indexed Knowledge Base")
    st.write("Manage your RAG vector store documents. You can inspect chunk counts, content hashes, or remove individual files.")
    
    col_ref, col_spacer = st.columns([1, 5])
    with col_ref:
        if st.button("🔄 Refresh List", key="ref_docs", use_container_width=True):
            st.rerun()
            
    try:
        data = get_json(api_base, "/documents", headers)
        documents = data.get("documents", [])
        if not documents:
            st.info("💡 Knowledge base is currently empty. Login as an Admin and go to **🛠️ Admin Portal** to ingest documents.")
        else:
            for doc in documents:
                with st.container():
                    st.markdown(f"""
                    <div class="glass-card" style="padding: 1.2rem; margin-bottom: 0.6rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin: 0; color: #60a5fa;">📄 {doc.get('source')}</h4>
                                <p style="margin: 0.3rem 0 0 0; color: #94a3b8; font-size: 0.85rem;">
                                    <b>ID:</b> <code>{doc.get('doc_id')}</code> | <b>Chunks:</b> <span class="status-badge badge-blue">{doc.get('chunk_count')} chunks</span> | <b>Hash:</b> <code>{str(doc.get('content_hash'))[:10]}...</code>
                                </p>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.session_state.role == "admin":
                        col_del, col_blank = st.columns([1, 5])
                        with col_del:
                            if st.button("🗑️ Delete File & Embeddings", key=f"del_{doc.get('doc_id')}", use_container_width=True):
                                try:
                                    with st.spinner("Processing..."):
                                    requests.delete(f"{api_base}/admin/documents/{doc.get('doc_id')}", headers=headers, timeout=10)
                                    st.success(f"🗑️ Deleted file '{doc.get('source')}' from disk and removed its embeddings from Qdrant!")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Delete failed: {exc}")
                st.divider()
    except requests.RequestException as exc:
        st.error(f"Failed to load documents: {exc}")

def render_admin_portal_tab(api_base: str, headers: dict):
    st.markdown("### 🛠️ Document Ingestion & Index Control")
    st.write("Upload new knowledge documents, trigger hybrid vector index rebuilds via Arq worker, or reset the collection.")
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("#### 📤 Upload Documents to Storage")
    uploaded_files = st.file_uploader(
        "Select files (.pdf, .docx, .txt, .md, .html)",
        type=["txt", "md", "pdf", "docx", "html", "htm"],
        accept_multiple_files=True,
    )
    if uploaded_files and st.button("💾 Save Uploaded Files to Backend", type="primary"):
        try:
            files = [("files", (file.name, file.getvalue(), file.type or "application/octet-stream")) for file in uploaded_files]
            response = requests.post(
                f"{api_base}/admin/upload",
                headers=headers,
                files=files,
                timeout=120,
            )
            response.raise_for_status()
            st.success(f"✅ Successfully saved {len(uploaded_files)} file(s) to backend storage!")
            st.json(response.json())
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("#### ⚙️ Hybrid Vector Indexing")
    col1, col2 = st.columns(2)
    with col1:
        force = st.checkbox("⚠️ Force recreate index (wipes existing embeddings)")
        if st.button("🚀 Run Document Ingestion", use_container_width=True, type="primary"):
            try:
                res = post_json(api_base, "/admin/ingest", headers, {"data_dir": DATA_DIR, "force": force})
                st.json(res)
                if job_id := res.get("job_id"):
                    result = poll_job_status(api_base, headers, job_id, "Ingesting & embedding documents via Arq Worker...")
                    if result and result.get("status") == "SUCCESS":
                        st.success("✅ Ingestion complete! Switch to the 📚 Documents tab or click Refresh list to see your new documents.")
            except requests.RequestException as exc:
                st.error(f"Ingestion failed: {exc}")
    with col2:
        st.write("")
        if st.button("🗑️ Reset Entire Index", use_container_width=True):
            try:
                st.json(post_json(api_base, "/admin/reset", headers))
                st.success("Index reset successfully.")
            except requests.RequestException as exc:
                st.error(f"Reset failed: {exc}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("#### 🗑️ One-Click Post-Ingestion File & Embedding Management")
    st.write("Easily remove uploaded files from storage and wipe their vector embeddings in one click after running ingestion.")
    try:
        docs_res = get_json(api_base, "/documents", headers)
        ingested_docs = docs_res.get("documents", [])
        if not ingested_docs:
            st.caption("No ingested documents currently found.")
        else:
            selected_to_delete = []
            for doc in ingested_docs:
                col_name, col_btn = st.columns([3, 1])
                with col_name:
                    if st.checkbox(f"📄 **{doc.get('source')}** (`{doc.get('chunk_count')} chunks`)", key=f"adm_chk_{doc.get('doc_id')}"):
                        selected_to_delete.append(doc)
                with col_btn:
                    if st.button("🗑️ Delete (1-Click)", key=f"adm_del_{doc.get('doc_id')}", use_container_width=True):
                        try:
                            with st.spinner("Processing..."):
                                    requests.delete(f"{api_base}/admin/documents/{doc.get('doc_id')}", headers=headers, timeout=10)
                            st.success(f"🗑️ Deleted file '{doc.get('source')}' and removed its embeddings!")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Delete failed: {exc}")
            if selected_to_delete:
                st.write("")
                if st.button(f"🗑️ Delete {len(selected_to_delete)} Selected File(s) & Embeddings in One Click", type="primary", use_container_width=True):
                    for d in selected_to_delete:
                        try:
                            requests.delete(f"{api_base}/admin/documents/{d.get('doc_id')}", headers=headers, timeout=10)
                        except requests.RequestException as e:
                st.error(f"⚠️ Connection error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
                    st.success(f"🗑️ Successfully deleted {len(selected_to_delete)} file(s) and removed their embeddings!")
                    st.rerun()
    except Exception as exc:
        st.caption(f"Could not load ingested documents: {exc}")
    st.markdown('</div>', unsafe_allow_html=True)

def render_evaluation_tab(api_base: str, headers: dict):
    st.markdown("### 📊 Automated Quality Assessment (RAGAS)")
    st.write("Evaluate how accurately and faithfully the copilot answers support questions using the RAGAS framework.")
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    if st.button("🚀 Run RAG Evaluation Now", type="primary"):
        try:
            res = post_json(api_base, "/admin/eval", headers)
            st.json(res)
            if job_id := res.get("job_id"):
                poll_job_status(api_base, headers, job_id, "Running RAGAS evaluation via Arq Worker... This may take 1-2 minutes.")
            st.success("Evaluation task dispatched!")
        except requests.RequestException as exc:
            st.error(f"Evaluation failed: {exc}. Ensure you have remaining OpenRouter credits/limits.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    try:
        res = get_json(api_base, "/admin/eval", headers)
        report_text = res.get("report", "No evaluation report available.")
        col_hdr, col_dl = st.columns([3, 1])
        with col_hdr:
            st.markdown("#### 📑 Latest Evaluation Report")
        with col_dl:
            if report_text and report_text != "No evaluation report available.":
                st.download_button(
                    label="📥 Download Log (eval_report.md)",
                    data=report_text,
                    file_name="eval_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                    type="primary",
                )
        st.markdown(f'<div class="glass-card">{report_text}</div>', unsafe_allow_html=True)
    except requests.RequestException:
        st.markdown("#### 📑 Latest Evaluation Report")
        st.info("💡 No evaluation report available yet. Click the button above to run your first evaluation!")

def render_langsmith_tab(api_base: str, headers: dict):
    st.markdown("### 📈 Observability & Tracing (LangSmith)")
    st.write("Monitor RAG agent steps, prompt tokens, and latency in real-time by adding these variables to your `.env`:")
    st.code("LANGCHAIN_TRACING_V2=true\nLANGCHAIN_API_KEY=your_langsmith_api_key\nLANGCHAIN_PROJECT=\"Support Docs Copilot\"", language="env")

    st.divider()
    st.markdown("#### 🔍 System Readiness Diagnostics")
    st.caption(f"Backend API Base URL: `{api_base}`")
    try:
        ready_data = get_json(api_base, "/ready", headers)
        cols = st.columns(3)
        with cols[0]:
            st.metric("Overall Status", "🟢 Ready" if ready_data.get("ready") else "🟡 Degraded")
        with cols[1]:
            st.metric("Vector Store", "🟢 Online" if ready_data.get("vector_store") else "🔴 Offline")
        with cols[2]:
            st.metric("LLM Provider", "🟢 Connected" if ready_data.get("llm") else "🔴 Offline")
        st.json(ready_data)
    except requests.RequestException as exc:
        st.error(f"Readiness check failed: {exc}")

def render_observability_dashboard_tab(api_base: str, headers: dict):
    st.markdown("### 👀 Live Session Observability Dashboard")
    st.write("Monitor ongoing user chat threads across the enterprise, inspect RAG source citations, and inject supervisor guidance.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### 🧵 Active Enterprise Threads")
        if st.button("🔄 Refresh Live Sessions", key="ref_obs", use_container_width=True):
            st.rerun()
        try:
            res = get_json(api_base, "/api/v1/admin/sessions", headers)
            all_sess = res.get("sessions", [])
            if not all_sess:
                st.info("No active user sessions found.")
                selected_sess = None
            else:
                all_sess.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
                options = {}
                for s in all_sess:
                    uid = s.get("user_id", "unknown")
                    sid = s["session_id"]
                    preview = s.get("last_preview", sid[:8] + "...")
                    t_val = s.get("updated_at", time.time())
                    t_str = time.strftime('%H:%M:%S', time.localtime(t_val)) if t_val else "recently"
                    label = f"[{t_str}] 👤 {uid} | {preview} ({sid[:6]})"
                    options[label] = (uid, sid)
                selected_label = st.radio("Select Thread (Sorted by Recent Activity):", list(options.keys()), key="obs_radio")
                selected_sess = options[selected_label] if selected_label else None
        except Exception as exc:
            st.error(f"Failed to fetch live sessions: {exc}")
            selected_sess = None
            
    with col2:
        st.markdown("#### 🔬 Live Thread Inspection & Intervention")
        if selected_sess:
            target_uid, target_sid = selected_sess
            try:
                thread_res = get_json(api_base, f"/api/v1/admin/sessions/{target_uid}/{target_sid}/messages", headers)
                msgs = thread_res.get("messages", [])
                summary = thread_res.get("summary")
                
                if summary:
                    st.markdown(f'<div class="glass-card" style="border-left: 4px solid #38bdf8;"><b>🧠 Dense Background Memory Summary:</b><br>{summary}</div>', unsafe_allow_html=True)
                    
                st.markdown(f"**Viewing Session:** `{target_sid}` | **User Account:** `{target_uid}`")
                
                with st.container(height=400, border=True):
                    for m in msgs:
                        role_icon = "👤 User" if m["role"] == "user" else ("👑 Supervisor" if m["role"] == "supervisor" else "🤖 Copilot")
                        st.markdown(f"**{role_icon}** ({time.strftime('%H:%M:%S', time.localtime(m.get('timestamp', time.time())))}):")
                        st.markdown(m.get("content", ""))
                        if sources := m.get("sources"):
                            with st.expander(f"📚 Inspect {len(sources)} Cited RAG Sources (Confidence: {m.get('confidence', 0.0)*100:.0f}%)"):
                                st.json(sources)
                        st.divider()
                        
                st.markdown("#### 🚨 Inject Supervisor Guidance")
                intervene_msg = st.text_input("Type clarification or correction message for this thread...", key="inv_input")
                if st.button("Inject Message into Thread", type="primary", key="inv_btn"):
                    if intervene_msg:
                        post_json(api_base, f"/api/v1/admin/sessions/{target_uid}/{target_sid}/message", headers, {"message": intervene_msg, "role": "supervisor"})
                        st.success("Supervisor intervention injected successfully!")
                        st.rerun()
            except Exception as exc:
                st.error(f"Could not load thread details: {exc}")
        else:
            st.caption("Select an active thread from the left column to inspect chat history, verify citations, and intervene.")

def render_admin(api_base: str, headers: dict):
    if st.session_state.role == "admin":
        obs_tab, admin_tab, eval_tab, langsmith_tab = st.tabs([
            "👀 Live Observability",
            "🛠️ Admin Portal", 
            "📊 RAGAS Evaluation", 
            "📈 LangSmith & Observability"
        ])
        with obs_tab:
            render_observability_dashboard_tab(api_base, headers)
        with admin_tab:
            render_admin_portal_tab(api_base, headers)
        with eval_tab:
            render_evaluation_tab(api_base, headers)
        with langsmith_tab:
            render_langsmith_tab(api_base, headers)
    else:
        st.error("Unauthorized access to Admin section.")
