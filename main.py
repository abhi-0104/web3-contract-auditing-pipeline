import uuid
import sys
from graph import app
from eval import log_eval, get_stats
from db import VectorDB

def print_stats(tenant_id):
    stats = get_stats(tenant_id)
    if stats:
        print(f"\n--- Metrics for {tenant_id} ---")
        print(f"Total Audits: {stats[0]['Total Audits']}")
        print(f"True Positives: {stats[0]['True Positives']}")
        print(f"False Positives: {stats[0]['False Positives']}\n")

def main():
    print("Welcome to the Multi-Tenant AI Code Reviewer!")
    tenant_id = input("Enter tenant ID (tenant_a or tenant_b): ").strip().lower()
    if tenant_id not in ['tenant_a', 'tenant_b']:
        print("Invalid tenant ID. Exiting.")
        sys.exit(1)
        
    print_stats(tenant_id)
    
    print("Enter the Python code snippet to review (type 'EOF' on a new line when done):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == 'EOF':
            break
        lines.append(line)
        
    user_code = "\n".join(lines)
    
    if not user_code.strip():
        print("No code provided. Exiting.")
        sys.exit(0)
    
    # LangGraph requires a unique thread_id for checkpointing memory
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "tenant_id": tenant_id,
        "user_code": user_code,
        "retrieved_context": "",
        "analysis_result": "",
        "human_feedback": ""
    }
    
    print("\n[System] Running Retrieve and Analyze nodes...")
    for event in app.stream(initial_state, config):
        for k, v in event.items():
            if k == 'retrieve':
                print(f"[Node: Retrieve] Fetched past bugs from {tenant_id} database.")
            elif k == 'analyze':
                print("[Node: Analyze] AI analysis complete.\n")
                print("--- AI CODE REVIEW ---")
                print(v.get('analysis_result', ''))
                print("----------------------\n")
    
    # Graph is interrupted before human_review
    # Human in the loop happens now
    
    print("[System] Human-in-the-loop: Was this analysis correct?")
    feedback = input("Type 'TP' for True Positive or 'FP' for False Positive: ").strip().upper()
    
    is_tp = feedback == 'TP'
    log_eval(tenant_id, is_tp)
    
    if not is_tp:
        print("\n[System] Registering False Positive...")
        correct_desc = input("Please provide a brief description of the actual bug (or why AI was wrong): ")
        
        # Append correction to ChromaDB
        print(f"[System] Adding human correction to {tenant_id} vector DB to improve future retrieval...")
        try:
            db = VectorDB()
            docs = [user_code]
            metas = [{"description": "HUMAN CORRECTION: " + correct_desc, "bug_id": f"CORRECTION-{uuid.uuid4().hex[:6]}"}]
            ids = [str(uuid.uuid4())]
            db.insert(tenant_id, docs, metas, ids)
            print("[System] Successfully updated vector database!")
        except Exception as e:
            print(f"[System] Error updating vector database: {e}")
    else:
        print("\n[System] Registered True Positive.")
        
    # Resume the graph to finish
    print("[System] Resuming graph to finish execution...")
    app.update_state(config, {"human_feedback": "True Positive" if is_tp else "False Positive"})
    
    for event in app.stream(None, config):
        pass # Completes the graph
        
    print_stats(tenant_id)

if __name__ == "__main__":
    main()
