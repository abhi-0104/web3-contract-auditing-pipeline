from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from db import VectorDB
import os
from dotenv import load_dotenv

# Load secret API keys from the secure hidden folder
load_dotenv(".secrets/.env")

# Define the state
class GraphState(TypedDict):
    tenant_id: str
    user_code: str
    retrieved_context: str
    analysis_result: str
    human_feedback: str  # 'True Positive' or 'False Positive'

db = VectorDB()
llm = ChatGroq(
    model_name="openai/gpt-oss-120b",
    temperature=1,
    max_tokens=8192,
    model_kwargs={
        "top_p": 1,
    }
)

def json_to_toon(data: list):
    """Converts a list of dicts to Token Oriented Object Notation (TOON) to save LLM tokens."""
    if not data:
        return "No historical bugs found."
        
    toon_lines = ["HistoricalBugs:"]
    for i, item in enumerate(data):
        toon_lines.append(f"  Bug_{i+1}:")
        for k, v in item.items():
            if isinstance(v, str) and '\n' in v:
                indented_v = "      " + v.replace('\n', '\n      ')
                toon_lines.append(f"    {k}:\n{indented_v}")
            else:
                toon_lines.append(f"    {k}: {v}")
    return "\n".join(toon_lines)

def retrieve_node(state: GraphState):
    tenant_id = state["tenant_id"]
    user_code = state["user_code"]
    
    # Query vector database
    results = db.query(tenant_id, [user_code], n_results=3)
    
    # Extract structural historical data (JSON-like)
    historical_bugs_json = []
    if results and results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i] if results['metadatas'] else {}
            historical_bugs_json.append({
                "description": meta.get("description", "Unknown Description"),
                "severity": meta.get("severity", "Unknown"),
                "cwe_class": meta.get("cwe", "Unknown"),
                "code_snippet": doc
            })
            
    # Compile the JSON data down to TOON to save context tokens!
    context = json_to_toon(historical_bugs_json)
            
    return {"retrieved_context": context}

def analyze_node(state: GraphState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert AI Smart Contract Auditor for a specific Web3 company tenant.
You must look for vulnerabilities in the uploaded solidity smart contract code, referencing past known bugs from this tenant provided in TOON format.
You MUST output your response as a valid JSON object matching this exact schema:
{{
    "cwe_class": "Reentrancy" | "Access Control" | "Oracle Manipulation" | "Frontrunning" | "Logic Flaw" | "Unchecked Call" | "Other",
    "severity": "Info" | "Low" | "Medium" | "High" | "Critical",
    "accuracy_score": 1-5,
    "exploitability_score": 1-5,
    "remediation_score": 1-5,
    "verdict_rationale": "Detailed explanation of the vulnerability and why these scores were chosen."
}}
Do NOT output any other text or markdown formatting before or after the JSON."""),
        ("user", "Here are some past known bugs from our company for context in TOON format:\n\n{context}\n\nHere is the new smart contract code to review:\n\n{code}\n\nPlease analyze the new code for potential vulnerabilities, paying special attention to related issues from our past TOON bugs.")
    ])
    
    chain = prompt | llm
    res = chain.invoke({
        "context": state.get("retrieved_context", "None"),
        "code": state["user_code"]
    })
    
    return {"analysis_result": res.content}

def human_review_node(state: GraphState):
    # This node doesn't actually do anything in terms of computation.
    # It just serves as a breakpoint where LangGraph will pause execution.
    return {"human_feedback": state.get("human_feedback", "")}

# Build the graph
workflow = StateGraph(GraphState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("human_review", human_review_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "analyze")
workflow.add_edge("analyze", "human_review")
workflow.add_edge("human_review", END)

# Compile with memory so it can be interrupted
memory = MemorySaver()
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]
)
