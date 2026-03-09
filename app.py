import streamlit as st
import uuid
import pandas as pd
import pandas as pd
from graph import app as langgraph_app
from eval import log_eval, get_stats, log_dataset_record
from db import VectorDB

# --- Page Config ---
st.set_page_config(
    page_title="Web3 Security Auditor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .metric-card {
        background-color: #1e1e2e;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #cba6f7;
    }
    .metric-label {
        font-size: 1rem;
        color: #a6adc8;
    }
    .stTextArea textarea {
        background-color: #181825;
        color: #cdd6f4;
        font-family: 'Courier New', Courier, monospace;
    }
    .success-alert { color: #a6e3a1; font-weight: bold; }
    .warning-alert { color: #f9e2af; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- Session State Management ---
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if 'stage' not in st.session_state:
    st.session_state.stage = 'input'  # input -> analysis -> feedback -> done
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = ""
if 'retrieved_context' not in st.session_state:
    st.session_state.retrieved_context = ""
if 'user_code' not in st.session_state:
    st.session_state.user_code = ""
if 'current_tenant' not in st.session_state:
    st.session_state.current_tenant = "tenant_a"

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Configuration")
    tenant_choice = st.selectbox(
        "Select Tenant",
        options=["tenant_a", "tenant_b"],
        format_func=lambda x: "Tenant A (DeFi Protocol)" if x == "tenant_a" else "Tenant B (NFT Marketplace)",
        index=0 if st.session_state.current_tenant == "tenant_a" else 1
    )
    
    # If tenant changes, reset the state
    if tenant_choice != st.session_state.current_tenant:
        st.session_state.current_tenant = tenant_choice
        st.session_state.stage = 'input'
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()
        
    st.markdown("---")
    st.subheader("📊 Tenant Metrics")
    
    # Refresh metrics
    stats = get_stats(st.session_state.current_tenant)
    if stats:
        s = stats[0]
        st.markdown(f'<div class="metric-card"><div class="metric-value">{s["Total Audits"]}</div><div class="metric-label">Total Audits</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#a6e3a1;">{s["True Positives"]}</div><div class="metric-label">True Positives</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f38ba8;">{s["False Positives"]}</div><div class="metric-label">False Positives</div></div>', unsafe_allow_html=True)
    else:
        st.info("No stats available yet.")
        
    st.markdown("---")
    if st.button("Reset Session", use_container_width=True):
        st.session_state.stage = 'input'
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.user_code = ""
        st.rerun()

# --- Main Area ---
st.title("🤖 Web3 Smart Contract AI Auditor")
st.markdown("RAG-Powered continuous learning AI security reviewer. Upload Solidity smart contracts below to isolated collections.")

# --- STAGE: INPUT ---
if st.session_state.stage == 'input':
    with st.container(border=True):
        st.subheader("📝 Submit Code for Review")
        code_input = st.text_area(
            "Paste Solidity Snippet", 
            value=st.session_state.user_code,
            height=250, 
            placeholder="function withdraw() public {\n    // code\n}"
        )
        
        if st.button("🚀 Analyze Code", type="primary"):
            if code_input.strip():
                st.session_state.user_code = code_input
                st.session_state.stage = 'analysis'
                st.rerun()
            else:
                st.warning("Please enter some code first!")

# --- STAGE: ANALYSIS ---
elif st.session_state.stage == 'analysis':
    st.info("Analyzing Code with LangGraph & Groq...")
    
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    initial_state = {
        "tenant_id": st.session_state.current_tenant,
        "user_code": st.session_state.user_code,
        "retrieved_context": "",
        "analysis_result": "",
        "human_feedback": ""
    }
    
    with st.spinner("Retrieving historical bugs and analyzing..."):
        # Run graph
        for event in langgraph_app.stream(initial_state, config):
            for k, v in event.items():
                if k == 'retrieve':
                    st.session_state.retrieved_context = v.get("retrieved_context", "")
                elif k == 'analyze':
                    st.session_state.analysis_result = v.get("analysis_result", "")

        st.session_state.stage = 'feedback'
        st.rerun()

# --- STAGE: FEEDBACK ---
elif st.session_state.stage == 'feedback':
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.container(border=True):
            st.subheader("📚 RAG Historical Context")
            if st.session_state.retrieved_context:
                st.markdown(st.session_state.retrieved_context)
            else:
                st.info("No relevant context found.")
                
        with st.container(border=True):
            st.subheader("📝 Submitted Code")
            st.code(st.session_state.user_code, language="solidity")

    with col2:
        with st.container(border=True):
            st.subheader("🧠 AI Analysis (Groq)")
            st.markdown(st.session_state.analysis_result)
            
        st.markdown("### 👨‍⚖️ Auditor Feedback Loop")
        st.markdown("Provide feedback or corrections. This data drives continuous model training (RLHF) and dynamic RAG updates.")
        
        # Taxonomy Inputs
        cwe_class = st.selectbox("Vulnerability Class", ["Reentrancy", "Access Control", "Oracle Manipulation", "Frontrunning", "Logic Flaw", "Unchecked Call", "Other"])
        severity = st.select_slider("Severity", ["Info", "Low", "Medium", "High", "Critical"], value="Medium")
        
        st.markdown("#### Evaluation Rubric (1-5)")
        r1, r2, r3 = st.columns(3)
        acc = r1.number_input("Detection Accuracy", min_value=1, max_value=5, value=3)
        exp = r2.number_input("Exploitability", min_value=1, max_value=5, value=3)
        rem = r3.number_input("Remediation", min_value=1, max_value=5, value=3)
        rubrics = {"accuracy": acc, "exploitability": exp, "remediation": rem}
        
        auditor_feedback = st.text_area("Detailed Feedback / Correction (Required for false cases):", placeholder="e.g. This is a false positive because the database uses lock-row semantics...")
        
        if st.button("🚀 Submit Audit Feedback", type="primary", use_container_width=True):
            # Internal logic to classify as TP / FP based on accuracy rubric
            is_true_positive = acc >= 3
            verdict = "True Positive" if is_true_positive else "False Positive"
            
            # Log to PostgreSQL Metrics
            log_eval(st.session_state.current_tenant, is_true_positive)
            
            # Merge case data and feedback, then store to Pinecone (Continual RAG Learning)
            if not is_true_positive and auditor_feedback:
                db = VectorDB()
                # Emphasize the correction in the document for vectors
                vector_doc = f"CODE:\n{st.session_state.user_code}\n\nCORRECTION:\n{auditor_feedback}"
                metas = [{
                    "description": "HUMAN CORRECTION: " + auditor_feedback,
                    "bug_id": f"CORRECTION-{uuid.uuid4().hex[:6]}",
                    "severity": severity,
                    "cwe": cwe_class
                }]
                ids = [str(uuid.uuid4())]
                db.insert(st.session_state.current_tenant, [vector_doc], metas, ids)
            
            # Record explicit Chosen/Rejected preference data to JSONL (Continual Model Training)
            failure_mode = "Context Miss/Hallucination" if not is_true_positive else ""
            log_dataset_record(
                tenant_id=st.session_state.current_tenant,
                code_snippet=st.session_state.user_code,
                rag_context=st.session_state.retrieved_context,
                ai_analysis=st.session_state.analysis_result,
                human_correction=auditor_feedback,
                verdict=verdict,
                severity=severity,
                vulnerability_class=cwe_class,
                failure_mode=failure_mode,
                rubric_scores=rubrics
            )
            
            # Resume LangGraph execution
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            langgraph_app.update_state(config, {"human_feedback": auditor_feedback})
            for event in langgraph_app.stream(None, config):
                pass
                
            st.session_state.stage = 'done'
            st.rerun()
                        
# --- STAGE: DONE ---
elif st.session_state.stage == 'done':
    st.balloons()
    st.success("Review process completed successfully! Evaluation metrics have been updated.")
    
    if st.button("Start New Review", type="primary"):
        st.session_state.stage = 'input'
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.user_code = ""
        st.rerun()
