import os
import json
from typing import List, Optional, Dict
from pydantic import BaseModel
from google import genai
from google.genai import types
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Using the key found in .env, which belongs to searchapi.io according to user instructions
SEARCHAPI_API_KEY = os.environ.get("SERP_API_KEY") 
PREFERENCE_FILE = "preference.md"

client = genai.Client(api_key=GEMINI_API_KEY)

class Product(BaseModel):
    name: str
    price: Optional[str] = None
    store: Optional[str] = None
    link: str
    image: Optional[str] = None

class AgentState(BaseModel):
    time: Optional[str] = None
    occasion: Optional[str] = None
    weather: Optional[str] = None
    affordability: Optional[str] = None
    preferences: Optional[str] = None
    history: List[Dict[str, str]] = []

def read_preferences() -> str:
    if not os.path.exists(PREFERENCE_FILE):
        return ""
    with open(PREFERENCE_FILE, "r") as f:
        return f.read()

def update_preferences(new_content: str):
    if not new_content or new_content.strip() == "": return
    with open(PREFERENCE_FILE, "a") as f:
        f.write(f"\n{new_content}")

def search_google_shopping(query: str) -> List[Product]:
    """
    Uses SearchApi.io Google Shopping engine.
    """
    if not SEARCHAPI_API_KEY:
        print("   ⚠️ SEARCHAPI_API_KEY (SERP_API_KEY) missing.")
        return []

    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SEARCHAPI_API_KEY,
        "gl": "in",
        "hl": "en",
        "location": "India"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        products = []
        results = data.get("shopping_results", [])
        
        # Taking top 6 results to be judicial
        for r in results[:6]:
            products.append(Product(
                name=r.get("title", "Unknown Product"),
                price=r.get("price", "N/A"),
                store=r.get("source", "Store"),
                link=r.get("product_link") or r.get("link"),
                image=r.get("thumbnail")
            ))
        return products
    except Exception as e:
        print(f"   ❌ SearchApi Error: {e}")
        return []

class FashionAgent:
    def __init__(self, model_name: str):
        self.model = model_name

    def process_query(self, user_query: str, state: AgentState):
        prefs = read_preferences()
        state.history.append({"role": "user", "content": user_query})
        
        # 1. Assessment
        assessment_prompt = f"""
        Current State: {state.json()}
        User Preferences (from file): {prefs}
        New User Query: {user_query}

        Assess if you have enough information for: Time, Occasion, Weather, Budget, Style.
        
        Return JSON with:
        - "updated_state": updated AgentState object (only update fields we now know)
        - "new_preferences": any new long-term preference for preference.md (string or null)
        - "is_ready": boolean (true ONLY if you have enough info to suggest specific products)
        - "response": clarifying question if not ready. Be very brief.
        """

        assessment = client.models.generate_content(
            model=self.model,
            contents=assessment_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        res = json.loads(assessment.text)
        
        if res.get("new_preferences"):
            update_preferences(res["new_preferences"])
        
        # Update local state
        new_state_data = res.get("updated_state", {})
        for key, value in new_state_data.items():
            if hasattr(state, key) and value:
                setattr(state, key, value)

        if not res.get("is_ready"):
            state.history.append({"role": "assistant", "content": res["response"]})
            return res["response"], [], state

        # 2. Search & Suggest
        search_query_prompt = f"""
        Build a search query for specific fashion products. 
        Context: {state.occasion}, {state.weather}, budget {state.affordability}, style {state.preferences} and {prefs}.
        Return ONLY the query string. Focus on the core pieces.
        """
        
        search_q_res = client.models.generate_content(
            model=self.model,
            contents=search_query_prompt
        )
        search_query = search_q_res.text.strip().strip('"')
        
        print(f"   🔍 Searching Google Shopping for: {search_query}")
        products = search_google_shopping(search_query)
        
        if not products:
            response_text = "I couldn't find specific products matching that exactly. Maybe try a broader budget or different style?"
            state.history.append({"role": "assistant", "content": response_text})
            return response_text, [], state

        final_response_prompt = f"""
        Suggest a specific outfit using these items: {json.dumps([p.dict() for p in products])}
        Focus heavily on the products found. Minimum general advice. 
        Explain why this specific combination works for {state.occasion} in {state.weather}.
        """
        
        final_res = client.models.generate_content(
            model=self.model,
            contents=final_response_prompt
        )
        
        response_text = final_res.text
        state.history.append({"role": "assistant", "content": response_text})
        
        return response_text, products, state
