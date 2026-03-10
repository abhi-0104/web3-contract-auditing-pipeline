from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import uuid
import json
from datetime import datetime, timedelta
from jose import JWTError, jwt

# Internal Modules
from auth_db import init_auth_db, create_user, get_user, verify_password
from graph import app as langgraph_app
from eval import log_eval, get_stats, log_dataset_record
from db import VectorDB
from dispute_db import init_disputes_db, add_dispute, get_pending_disputes, resolve_dispute

# JWT Config
SECRET_KEY = "super-secret-key-keep-safe"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI(title="Web3 Auditor API")

init_auth_db()
init_disputes_db()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- AUTHENTICATION ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        user = get_user(username)
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

# Pydantic Models for Requests
class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "junior"

class AuditRequest(BaseModel):
    tenant_id: str
    user_code: str

class AuditSubmit(BaseModel):
    tenant_id: str
    user_code: str
    retrieved_context: str
    analysis_result_raw: str
    ai_json_str: str
    cwe_class: str
    severity: str
    accuracy: int
    exploitability: int
    remediation: int
    auditor_feedback: str

class DisputeResolve(BaseModel):
    final_cwe: str
    final_sev: str
    final_rationale: str
    is_tp: bool

# --- ENDPOINTS ---
@app.post("/register")
def register(user: UserRegister, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "senior":
        raise HTTPException(status_code=403, detail="Seniors only: Management level required to provision accounts.")
    if user.role not in ["junior", "senior"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    success = create_user(user.username, user.password, user.role)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"msg": "User created successfully"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user["role"]}

@app.post("/audit/analyze")
def run_analysis(req: AuditRequest, current_user: dict = Depends(get_current_user)):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "tenant_id": req.tenant_id,
        "user_code": req.user_code,
        "retrieved_context": "",
        "analysis_result": "",
        "human_feedback": ""
    }
    
    retrieved_context = ""
    analysis_result = ""
    for event in langgraph_app.stream(initial_state, config):
        for k, v in event.items():
            if k == 'retrieve':
                retrieved_context = v.get("retrieved_context", "")
            elif k == 'analyze':
                analysis_result = v.get("analysis_result", "")
                
    return {"retrieved_context": retrieved_context, "analysis_result": analysis_result}

@app.post("/audit/submit")
def submit_audit(req: AuditSubmit, current_user: dict = Depends(get_current_user)):
    # Semantic Matcher Logic
    is_match = False
    try:
        ai_json = json.loads(req.ai_json_str)
        if req.cwe_class == ai_json.get("cwe_class") and req.severity == ai_json.get("severity"):
            is_match = True
    except:
        is_match = False

    if is_match:
        true_positive = req.accuracy >= 3
        rubrics = {"accuracy": req.accuracy, "exploitability": req.exploitability, "remediation": req.remediation}
        
        # SAVE LOGIC
        log_eval(req.tenant_id, true_positive)
        if not true_positive and req.auditor_feedback:
            db = VectorDB()
            vector_doc = f"CODE:\n{req.user_code}\n\nCORRECTION:\n{req.auditor_feedback}"
            metas = [{"description": "HUMAN CORRECTION: " + req.auditor_feedback, "bug_id": f"CORRECTION-{uuid.uuid4().hex[:6]}", "severity": req.severity, "cwe": req.cwe_class}]
            db.insert(req.tenant_id, [vector_doc], metas, [str(uuid.uuid4())])
            
        failure_mode = "Context Miss/Hallucination" if not true_positive else ""
        log_dataset_record(req.tenant_id, req.user_code, req.retrieved_context, req.analysis_result_raw, req.auditor_feedback, "True Positive" if true_positive else "False Positive", req.severity, req.cwe_class, failure_mode, rubrics)
        
        return {"status": "match", "message": "Written directly to databases"}
    else:
        dispute_id = str(uuid.uuid4())
        add_dispute(dispute_id, req.tenant_id, req.user_code, req.retrieved_context, req.analysis_result_raw, req.cwe_class, req.severity, req.accuracy, req.exploitability, req.remediation, req.auditor_feedback)
        return {"status": "disputed", "message": "Dispute logged to SQLite holding queue."}

@app.get("/disputes")
def get_disputes(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "senior":
        raise HTTPException(status_code=403, detail="Seniors only")
    return get_pending_disputes()

@app.post("/disputes/{dispute_id}/resolve")
def resolve_dispute_endpoint(dispute_id: str, req: DisputeResolve, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "senior":
        raise HTTPException(status_code=403, detail="Seniors only")
        
    disputes = get_pending_disputes()
    target = next((d for d in disputes if d["id"] == dispute_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Dispute not found")
        
    rubrics = {"accuracy": target['junior_accuracy'], "exploitability": target['junior_exploitability'], "remediation": target['junior_remediation']}
    
    # Write Final truth
    log_eval(target['tenant_id'], req.is_tp)
    if not req.is_tp and req.final_rationale:
        db = VectorDB()
        vector_doc = f"CODE:\n{target['user_code']}\n\nCORRECTION:\n{req.final_rationale}"
        metas = [{"description": "HUMAN CORRECTION: " + req.final_rationale, "bug_id": f"CORRECTION-{uuid.uuid4().hex[:6]}", "severity": req.final_sev, "cwe": req.final_cwe}]
        db.insert(target['tenant_id'], [vector_doc], metas, [str(uuid.uuid4())])
        
    failure_mode = "Context Miss/Hallucination" if not req.is_tp else ""
    log_dataset_record(target['tenant_id'], target['user_code'], target['rag_context'], target['ai_analysis_json'], req.final_rationale, "True Positive" if req.is_tp else "False Positive", req.final_sev, req.final_cwe, failure_mode, rubrics)

    resolve_dispute(dispute_id)
    resolve_dispute(dispute_id)
    return {"status": "resolved"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
