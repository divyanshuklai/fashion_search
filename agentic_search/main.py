from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from agent import FashionAgent, AgentState
import uuid
import os
import json
from typing import Optional

MODEL_NAME = "gemma-4-31b-it"

app = FastAPI(title="Agentic Fashion Assistant")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Hidden directory for sessions
SESSIONS_DIR = ".agent_sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

class ChatQuery(BaseModel):
    query: str
    session_id: Optional[str] = None

def get_session_path(session_id: str):
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")

def load_session(session_id: str) -> AgentState:
    if not session_id or session_id in ["null", "undefined", "None"]:
        return AgentState()
    
    path = get_session_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                state = AgentState(**data)
                print(f"   [SESSION] SUCCESS: Loaded session {session_id} ({len(state.history)} turns)")
                return state
        except Exception as e:
            print(f"   ❌ [SESSION] ERROR loading {session_id}: {e}")
            return AgentState()
    print(f"   🆕 [SESSION] NOT FOUND: Starting new for {session_id}")
    return AgentState()

def save_session(session_id: str, state: AgentState):
    path = get_session_path(session_id)
    try:
        with open(path, "w") as f:
            f.write(state.model_dump_json())
    except Exception as e:
        print(f"   ❌ [SESSION] ERROR saving {session_id}: {e}")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat_endpoint(request: ChatQuery):
    # Log exactly what arrived
    print(f"   [API] INCOMING session_id: '{request.session_id}'")
    
    # Determine the actual session ID to use
    if not request.session_id or request.session_id in ["null", "undefined", "None"]:
        session_id = str(uuid.uuid4())
        print(f"   [API] GENERATED new session_id: {session_id}")
    else:
        session_id = request.session_id
    
    state = load_session(session_id)
    
    agent = FashionAgent(model_name="gemma-4-31b-it")
    text, products, updated_state = agent.process_query(request.query, state)
    
    save_session(session_id, updated_state)
    
    print(f"   [API] OUTGOING session_id: {session_id} | Products: {len(products)}")
    return {
        "text": text,
        "products": [p.model_dump() for p in products],
        "session_id": session_id,
        "history": updated_state.history 
    }

@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    state = load_session(session_id)
    return {"history": state.history}

if __name__ == "__main__":
    # Crucial: ignore the sessions directory to prevent restart loops
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_excludes=[".agent_sessions/*"])