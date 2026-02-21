from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from naive_search import search_fashion_products

app = FastAPI(title="Fashion Discovery Chat")

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatQuery(BaseModel):
    query: str

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat_endpoint(request: ChatQuery):
    products = search_fashion_products(request.query)
    
    if not products:
        return {
            "text": "I couldn't find any products matching that query. Could you try rephrasing your search?",
            "products": []
        }
        
    return {
        "text": f"Got it! Here are some options that could work for '{request.query}':",
        "products": products
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
