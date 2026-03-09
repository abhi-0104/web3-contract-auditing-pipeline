import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, MetaData, Table

# Fallback to local sqlite if Postgres credentials aren't provided yet
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///evaluations.db")
DATASET_FILE = "training_dataset.jsonl"

engine = create_engine(DATABASE_URL)
metadata = MetaData()

evaluations_table = Table(
    'evaluations', metadata,
    Column('tenant_id', String, primary_key=True),
    Column('total_audits', Integer, default=0),
    Column('true_positives', Integer, default=0),
    Column('false_positives', Integer, default=0)
)
def init_eval():
    metadata.create_all(engine)

def log_eval(tenant_id: str, is_true_positive: bool):
    init_eval()
    
    with engine.begin() as conn:
        # Check if tenant exists
        result = conn.execute(evaluations_table.select().where(evaluations_table.c.tenant_id == tenant_id)).fetchone()
        
        if result is None:
            conn.execute(evaluations_table.insert().values(
                tenant_id=tenant_id, 
                total_audits=0, 
                true_positives=0, 
                false_positives=0
            ))
            
        update_stmt = evaluations_table.update().where(evaluations_table.c.tenant_id == tenant_id)
        
        if is_true_positive:
            conn.execute(update_stmt.values(
                total_audits=evaluations_table.c.total_audits + 1,
                true_positives=evaluations_table.c.true_positives + 1
            ))
        else:
            conn.execute(update_stmt.values(
                total_audits=evaluations_table.c.total_audits + 1,
                false_positives=evaluations_table.c.false_positives + 1
            ))

def log_dataset_record(
    tenant_id: str,
    code_snippet: str,
    rag_context: str,
    ai_analysis: str,
    human_correction: str,
    verdict: str,
    severity: str,
    vulnerability_class: str,
    failure_mode: str,
    rubric_scores: dict
):
    """
    Logs structured data into a JSONLines file, generating a dataset suitable for
    RLHF, DPO, or SFT down the line. Records 'chosen' vs 'rejected' behavior.
    """
    is_fp = verdict == "False Positive"
    
    record = {
        "tenant_id": tenant_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "code_snippet": code_snippet,
        "rag_context": rag_context,
        "rejected_analysis": ai_analysis if is_fp else None,
        "chosen_analysis": human_correction if is_fp else ai_analysis,
        "metadata": {
            "verdict": verdict,
            "severity": severity,
            "vulnerability_class": vulnerability_class,
            "failure_mode": failure_mode if is_fp else None
        },
        "rubric_scores": rubric_scores
    }
    
    with open(DATASET_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")

def get_stats(tenant_id: str = None):
    init_eval()
    results = []
    
    with engine.connect() as conn:
        if tenant_id:
            stmt = evaluations_table.select().where(evaluations_table.c.tenant_id == tenant_id)
        else:
            stmt = evaluations_table.select()
            
        rows = conn.execute(stmt).fetchall()
        
        for row in rows:
            results.append({
                "tenant_id": row.tenant_id,
                "Total Audits": row.total_audits,
                "True Positives": row.true_positives,
                "False Positives": row.false_positives
            })
            
    return results
