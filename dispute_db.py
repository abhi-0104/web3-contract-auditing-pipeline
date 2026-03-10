import sqlite3
import json

DB_FILE = "disputes.db"

def init_disputes_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS disputes (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            user_code TEXT,
            rag_context TEXT,
            ai_analysis_json TEXT,
            junior_cwe TEXT,
            junior_severity TEXT,
            junior_accuracy INTEGER,
            junior_exploitability INTEGER,
            junior_remediation INTEGER,
            junior_rationale TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

def add_dispute(dispute_id, tenant_id, user_code, rag_context, ai_analysis_json, junior_cwe, junior_severity, junior_accuracy, junior_exploitability, junior_remediation, junior_rationale):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO disputes (id, tenant_id, user_code, rag_context, ai_analysis_json, junior_cwe, junior_severity, junior_accuracy, junior_exploitability, junior_remediation, junior_rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dispute_id, tenant_id, user_code, rag_context, ai_analysis_json, junior_cwe, junior_severity, junior_accuracy, junior_exploitability, junior_remediation, junior_rationale))
    conn.commit()
    conn.close()

def get_pending_disputes():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM disputes WHERE status='pending'")
    rows = c.fetchall()
    conn.close()
    
    disputes = []
    for row in rows:
        disputes.append({
            "id": row[0],
            "tenant_id": row[1],
            "user_code": row[2],
            "rag_context": row[3],
            "ai_analysis_json": row[4],
            "junior_cwe": row[5],
            "junior_severity": row[6],
            "junior_accuracy": row[7],
            "junior_exploitability": row[8],
            "junior_remediation": row[9],
            "junior_rationale": row[10]
        })
    return disputes

def resolve_dispute(dispute_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE disputes SET status='resolved' WHERE id=?", (dispute_id,))
    conn.commit()
    conn.close()
