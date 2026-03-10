import streamlit as st
import requests
import json
import pandas as pd

API_URL = "http://localhost:8000"

# --- Page Config ---
st.set_page_config(
    page_title="Maker-Checker Web3 Auditor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .metric-card { background-color: #1e1e2e; border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 20px;}
    .metric-value { font-size: 2rem; font-weight: bold; color: #cba6f7; }
    .metric-label { font-size: 1rem; color: #a6adc8; }
    .dispute-box { border-left: 5px solid #f38ba8; padding-left: 15px; margin-bottom: 20px;}
    .ai-box { border-left: 5px solid #89b4fa; padding-left: 15px; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'token' not in st.session_state: st.session_state.token = None
if 'role' not in st.session_state: st.session_state.role = None
if 'username' not in st.session_state: st.session_state.username = None
if 'stage' not in st.session_state: st.session_state.stage = 'input'
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = ""
if 'retrieved_context' not in st.session_state: st.session_state.retrieved_context = ""
if 'user_code' not in st.session_state: st.session_state.user_code = ""
if 'current_tenant' not in st.session_state: st.session_state.current_tenant = "tenant_a"

def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

# --- LOGIN SCREEN ---
if not st.session_state.token:
    st.title("🔒 Maker-Checker Pipeline")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("### 🔐 Secure Login")
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", type="primary"):
                resp = requests.post(f"{API_URL}/token", data={"username": l_user, "password": l_pass})
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.role = data["role"]
                    st.session_state.username = l_user
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    st.stop()

# --- SIDEBAR (Shared) ---
with st.sidebar:
    st.title(f"👤 {st.session_state.role.capitalize()} Portal")
    st.write(f"Logged in as: **{st.session_state.username}**")
    if st.button("Logout"):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.stage = 'input'
        st.rerun()
        
    st.markdown("---")
    tenant_choice = st.selectbox(
        "Select Tenant Context",
        options=["tenant_a", "tenant_b"],
        format_func=lambda x: "Tenant A (DeFi Protocol)" if x == "tenant_a" else "Tenant B (NFT Marketplace)",
        index=0 if st.session_state.current_tenant == "tenant_a" else 1
    )
    if tenant_choice != st.session_state.current_tenant:
        st.session_state.current_tenant = tenant_choice
        st.session_state.stage = 'input'
        st.rerun()
    
    if st.button("Reset Session", use_container_width=True):
        st.session_state.stage = 'input'
        st.session_state.user_code = ""
        st.rerun()

# ==================================================
# ROLE: JUNIOR AUDITOR (THE MAKER)
# ==================================================
if st.session_state.role == 'junior':
    st.title("🛡️ Junior Auditor Dashboard")

    if st.session_state.stage == 'input':
        with st.container(border=True):
            st.subheader("📝 Submit Code for Analysis")
            code_input = st.text_area("Paste Solidity Snippet", value=st.session_state.user_code, height=250)
            if st.button("🚀 Run AI Review", type="primary"):
                if code_input.strip():
                    st.session_state.user_code = code_input
                    st.session_state.stage = 'analysis'
                    st.rerun()

    elif st.session_state.stage == 'analysis':
        st.info("Analyzing Code via FastAPI & LangGraph...")
        with st.spinner("Retrieving bugs & enforcing JSON schema..."):
            resp = requests.post(
                f"{API_URL}/audit/analyze", 
                headers=get_headers(),
                json={"tenant_id": st.session_state.current_tenant, "user_code": st.session_state.user_code}
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.retrieved_context = data["retrieved_context"]
                st.session_state.analysis_result = data["analysis_result"]
                st.session_state.stage = 'feedback'
                st.rerun()
            else:
                st.error(f"API Error: {resp.text}")
                if st.button("Go Back"):
                    st.session_state.stage = 'input'
                    st.rerun()

    elif st.session_state.stage == 'feedback':
        col1, col2 = st.columns([1, 1])
        
        # Try parse AI JSON
        ai_json = None
        json_str_for_api = "{}"
        try:
            raw = st.session_state.analysis_result
            if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
            ai_json = json.loads(raw)
            json_str_for_api = json.dumps(ai_json)
        except:
             pass 
             
        with col1:
            with st.container(border=True):
                st.subheader("📝 Submitted Code")
                st.code(st.session_state.user_code, language="solidity")
            with st.container(border=True):
                st.subheader("🤖 AI Output (Structured Validation)")
                if ai_json: st.json(ai_json)
                else:
                    st.warning("Failed to parse strict JSON. Raw output:")
                    st.markdown(st.session_state.analysis_result)

        with col2:
            st.markdown("### 👨‍⚖️ Auditor Review Rubric")
            
            cwe_class = st.selectbox("Vulnerability Class", ["Reentrancy", "Access Control", "Oracle Manipulation", "Frontrunning", "Logic Flaw", "Unchecked Call", "Other"])
            severity = st.select_slider("Severity", ["Info", "Low", "Medium", "High", "Critical"], value="Medium")
            
            r1, r2, r3 = st.columns(3)
            acc = r1.number_input("Accuracy", min_value=1, max_value=5, value=3)
            exp = r2.number_input("Exploitability", min_value=1, max_value=5, value=3)
            rem = r3.number_input("Remediation", min_value=1, max_value=5, value=3)
            
            auditor_feedback = st.text_area("Rationale / Correction (Required if disputing):")
            
            if st.button("🚀 Submit Audit", type="primary", use_container_width=True):
                payload = {
                    "tenant_id": st.session_state.current_tenant,
                    "user_code": st.session_state.user_code,
                    "retrieved_context": st.session_state.retrieved_context,
                    "analysis_result_raw": st.session_state.analysis_result,
                    "ai_json_str": json_str_for_api,
                    "cwe_class": cwe_class,
                    "severity": severity,
                    "accuracy": acc,
                    "exploitability": exp,
                    "remediation": rem,
                    "auditor_feedback": auditor_feedback
                }
                resp = requests.post(f"{API_URL}/audit/submit", headers=get_headers(), json=payload)
                
                if resp.status_code == 200:
                    status = resp.json().get("status")
                    if status == "match":
                        st.session_state.stage = 'done_match'
                    else:
                        st.session_state.stage = 'done_dispute'
                    st.rerun()
                else:
                    st.error(f"Failed to submit: {resp.text}")

    elif st.session_state.stage == 'done_match':
        st.balloons()
        st.success("✅ Semantic Match Confirmed! Data successfully written to Vector Lake and Postgres Metrics by the FastAPI Backend.")
        if st.button("Audit Next Contract", type="primary"):
            st.session_state.stage = 'input'
            st.session_state.user_code = ""
            st.rerun()
            
    elif st.session_state.stage == 'done_dispute':
        st.warning("⚠️ Dispute Detected! Your taxonomy did not match the AI. Fast API has routed this to the Senior Reviewer Queue.")
        if st.button("Audit Next Contract", type="primary"):
            st.session_state.stage = 'input'
            st.session_state.user_code = ""
            st.rerun()

# ==================================================
# ROLE: SENIOR REVIEWER (THE CHECKER)
# ==================================================
elif st.session_state.role == 'senior':
    st.title("⚖️ Senior Reviewer Dispute Engine")
    
    resp = requests.get(f"{API_URL}/disputes", headers=get_headers())
    if resp.status_code != 200:
        st.error(f"Failed to load disputes: {resp.text}")
        st.stop()
        
    disputes = resp.json()
    
    st.markdown("---")
    st.subheader("👥 User Management (Admin)")
    with st.expander("Provision New User Account"):
        with st.form("register_form"):
            r_user = st.text_input("New Username")
            r_pass = st.text_input("New Password", type="password")
            r_role = st.selectbox("Role", ["junior", "senior"])
            if st.form_submit_button("Create Account", type="primary"):
                resp = requests.post(f"{API_URL}/register", headers=get_headers(), json={"username": r_user, "password": r_pass, "role": r_role})
                if resp.status_code == 200:
                    st.success(f"Account '{r_user}' provisioned successfully!")
                else:
                    st.error(resp.json().get("detail", "Registration failed"))
                    
    st.markdown("---")
    st.subheader("📋 Dispute Queue")
    
    if not disputes:
        st.success("🎉 The queue is empty! No active disputes.")
        st.stop()
        
    st.markdown(f"**Pending Disputes in Queue:** {len(disputes)}")
    
    for d in disputes:
        with st.expander(f"Dispute ID: {d['id'][:8]} | Tenant: {d['tenant_id']} | Jr Sev: {d['junior_severity']}", expanded=False):
            st.code(d['user_code'], language="solidity")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("<div class='ai-box'>", unsafe_allow_html=True)
                st.subheader("🤖 AI Original Logic")
                try:
                    raw = d['ai_analysis_json']
                    if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
                    st.json(json.loads(raw))
                except:
                    st.text(d['ai_analysis_json'])
                st.markdown("</div>", unsafe_allow_html=True)
                
            with c2:
                st.markdown("<div class='dispute-box'>", unsafe_allow_html=True)
                st.subheader("🧑‍💻 Junior Auditor Override")
                st.markdown(f"**CWE:** {d['junior_cwe']} | **Sev:** {d['junior_severity']}")
                st.markdown(f"**Rubrics:** Acc: {d['junior_accuracy']}, Exp: {d['junior_exploitability']}, Rem: {d['junior_remediation']}")
                st.markdown(f"**Junior Rationale:**\n{d['junior_rationale']}")
                st.markdown("</div>", unsafe_allow_html=True)
                
            st.markdown("### 🚦 Final Executive Resolution")
            with st.form(key=f"resolve_form_{d['id']}"):
                final_cwe = st.selectbox("Final CWE", ["Reentrancy", "Access Control", "Oracle Manipulation", "Frontrunning", "Logic Flaw", "Unchecked Call", "Other"], index=["Reentrancy", "Access Control", "Oracle Manipulation", "Frontrunning", "Logic Flaw", "Unchecked Call", "Other"].index(d['junior_cwe']) if d['junior_cwe'] in ["Reentrancy", "Access Control", "Oracle Manipulation", "Frontrunning", "Logic Flaw", "Unchecked Call", "Other"] else 6)
                final_sev = st.select_slider("Final Severity", ["Info", "Low", "Medium", "High", "Critical"], value=d['junior_severity'])
                final_rationale = st.text_area("Final Rationale (Saved to Dataset):", value=d['junior_rationale'])
                is_tp = st.checkbox("Mark as True Positive (AI was correct)", value=(d['junior_accuracy']>=3))
                
                if st.form_submit_button("Approve & Write to Databases", type="primary"):
                    payload = {
                        "final_cwe": final_cwe,
                        "final_sev": final_sev,
                        "final_rationale": final_rationale,
                        "is_tp": is_tp
                    }
                    resp = requests.post(f"{API_URL}/disputes/{d['id']}/resolve", headers=get_headers(), json=payload)
                    if resp.status_code == 200:
                        st.success(f"Resolved Conflict {d['id'][:8]}. Refreshing queue...")
                        st.rerun()
                    else:
                        st.error(f"Failed to resolve: {resp.text}")

