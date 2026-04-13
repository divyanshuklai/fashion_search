import os
import json
import re
from typing import List, Optional, Dict
from pydantic import BaseModel
from google import genai
from google.genai import types
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SEARCHAPI_API_KEY = os.environ.get("SEARCH_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

class Product(BaseModel):
    name: Optional[str] = "No name available"
    price: Optional[str] = None
    store: Optional[str] = None
    link: Optional[str] = None
    image: Optional[str] = None

class AgentState(BaseModel):
    history: List[Dict[str, str]] = []


def _extract_json_object(text: str) -> Dict:
    """Best-effort JSON parsing for model output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))

def search_fashion_items(query: str) -> Dict:
    print(f"   🎯 TOOL CALL: Searching for: {query}")
    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "google_shopping", "q": query, "api_key": SEARCHAPI_API_KEY,
        "gl": "in", "hl": "en", "location": "India"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        results = data.get("shopping_results", [])
        print(f"   🔍 API returned {len(results)} shopping results")
        
        if results and len(results) > 0:
            print(f"   DEBUG: First result keys: {list(results[0].keys())}")
        
        if "error" in data:
            print(f"   ❌ Search API error: {data['error']}")
        
        products = []
        for r in results:
            name = r.get("title")
            link = r.get("product_link") or r.get("offers_link") or r.get("link")
            if not name:
                continue
            products.append({
                "name": name, 
                "price": r.get("price"), 
                "store": r.get("seller") or r.get("source"), 
                "link": link, 
                "image": r.get("thumbnail")
            })
            if len(products) >= 6:
                break
        return {"products": products}
    except Exception as e:
        print(f"   ❌ Exception in search_fashion_items: {e}")
        return {"error": str(e)}

class FashionAgent:
    def __init__(self, model_name: str):
        self.model = model_name

    def _plan_next_step(self, gemini_contents):
        planner_config = types.GenerateContentConfig(
            system_instruction=(
                "You are a fashion shopping planner. Decide whether there is enough information to search a shopping endpoint. "
                "Be conservative: if the request is vague, incomplete, or ambiguous, ask exactly one short clarifying question. "
                "Only search when you are confident about the best outfit/category to look for. "
                "Return ONLY valid JSON with these keys: "
                "ready_to_search (boolean), search_query (string or null), clarifying_question (string or null), missing_info (array of strings), confidence (number from 0 to 1). "
                "When ready_to_search is true, search_query must be a compact shopping query with 2-5 keywords that captures the best inferred outfit. "
                "Do not repeat the user's full sentence in search_query."
            ),
            temperature=0,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=gemini_contents,
            config=planner_config,
        )

        text = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text += part.text

        plan = _extract_json_object(text)
        plan.setdefault("ready_to_search", False)
        plan.setdefault("search_query", None)
        plan.setdefault("clarifying_question", None)
        plan.setdefault("missing_info", [])
        plan.setdefault("confidence", 0)
        return plan

    def process_query(self, user_query: str, state: AgentState):
        # 1. Add current query to state
        state.history.append({"role": "user", "content": user_query})
        
        # 2. Build Gemini contents (ENTIRE history including current message)
        gemini_contents = []
        for m in state.history:
            role = "user" if m["role"] == "user" else "model"
            gemini_contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
        
        # 3. Let the model decide whether it is confident enough to search
        plan = self._plan_next_step(gemini_contents)

        if not plan.get("ready_to_search"):
            question = plan.get("clarifying_question")
            if not question:
                missing = plan.get("missing_info") or []
                if missing:
                    question = f"Could you share your {', '.join(missing[:3])}?"
                else:
                    question = "Could you share a bit more about the occasion, budget, and style you want?"

            state.history.append({"role": "model", "content": question})
            return question, [], state

        # 4. Tools and Config
        tools = [types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="search_fashion_items",
                description="Searches for fashion products using a compact shopping query inferred from the user's intent.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "A short shopping query the model infers from the user's needs."}
                    },
                    "required": ["query"]
                }
            )
        ])]

        config = types.GenerateContentConfig(
            system_instruction=(
                "You are a fashion assistant. The planner has already decided that enough information is available to search. "
                "Use the search_fashion_items tool with the compact shopping query from the planner."
            ),
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        )

        # 4. Generate
        response = client.models.generate_content(model=self.model, contents=gemini_contents, config=config)

        # 5. Extract
        response_text = ""
        found_products = []
        for candidate in response.candidates:
            has_function_call = any(
                getattr(part, "function_call", None) and part.function_call.name == "search_fashion_items"
                for part in candidate.content.parts
            )
            for part in candidate.content.parts:
                if part.text and not has_function_call:
                    response_text += part.text
                elif part.function_call and part.function_call.name == "search_fashion_items":
                    # Call it yourself
                    args = dict(part.function_call.args)
                    tool_result = search_fashion_items(**args)
                    if "products" in tool_result:
                        new_products = [Product(**p) for p in tool_result["products"]]
                        found_products.extend(new_products)
                        print(f"   ✅ FOUND {len(new_products)} products")
                    
                    response_text = "I found some options for you."
        
        if not response_text:
            response_text = "Here are some options I found."
        state.history.append({"role": "model", "content": response_text})
        return response_text, found_products, state
