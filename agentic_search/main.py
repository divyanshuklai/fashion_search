from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from agent import FashionAgent, AgentState
import uuid

MODEL_NAME = "gemma-4-31b-it"

app = FastAPI(title="Agentic Fashion Assistant")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory store for agent states
sessions = {}

class ChatQuery(BaseModel):
    query: str
    session_id: str = None

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat_endpoint(request: ChatQuery):
    session_id = request.session_id or str(uuid.uuid4())
    
    if session_id not in sessions:
        sessions[session_id] = AgentState()
    
    state = sessions[session_id]
    agent = FashionAgent(model_name=MODEL_NAME)
    
    text, products, updated_state = agent.process_query(request.query, state)
    
    # Save updated state
    sessions[session_id] = updated_state
    
    return {
        "text": text,
        "products": [p.dict() for p in products],
        "session_id": session_id
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
