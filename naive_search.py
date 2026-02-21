import os
import requests
import json
import random
from bs4 import BeautifulSoup
from tavily import TavilyClient
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY") # Ensure this is set

# Expanded List for Diversity (Indian Context)
STORES = [
    "myntra.com", "ajio.com", "tatacliq.com", "snitch.co.in", 
    "thehouseofrare.com", "bewakoof.com", "westside.com", 
    "pantaloons.com", "marksandspencer.in", "jaypore.com"
]

# Initialize Clients
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
# New SDK Initialization
client = genai.Client(api_key=GEMINI_API_KEY)

def get_og_image(url):
    """
    Visits the URL and extracts the 'og:image' meta tag.
    This gets the high-quality thumbnail used for social media sharing.
    """
    try:
        # User-Agent is CRITICAL. Without it, stores like Myntra block the request.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=3) # Fast timeout
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, "lxml")
        
        # Priority 1: Open Graph Image (The standard)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
            
        # Priority 2: Twitter Image
        twitter_image = soup.find("meta", name="twitter:image")
        if twitter_image and twitter_image.get("content"):
            return twitter_image["content"]

        return None
    except Exception:
        return None

def search_fashion_products(query):
    print(f"--- Method 1: Searching for '{query}' ---")
    
    # 1. SEARCH (Tavily)
    try:
        response = tavily_client.search(
            query=query, 
            search_depth="basic", 
            include_domains=STORES, # Force diversity
            country="india",
            max_results=20 # Fetch more to allow for filtering
        )
    except Exception as e:
        print(f"Tavily Error: {e}")
        return []

    # 2. PREPARE CONTEXT
    # We strip out the messy content and just give the LLM the basics to parse
    raw_context = "\n".join([
        f"Source {i}: {r['title']} | URL: {r['url']} | Snippet: {r['content'][:200]}" 
        for i, r in enumerate(response['results'])
    ])

    # 3. LLM PARSING (Using google-genai SDK)
    prompt = f"""
    Extract a list of distinct fashion products from these search results.
    
    Rules:
    - Return a valid JSON array of objects.
    - Keys: "name" (specific product name), "price" (extract if available, else null), "store" (extract from URL), "link".
    - Ignore generic "Shop All" or category pages. Only include specific product pages if possible.
    - If multiple products are listed in one snippet, pick the most relevant one.
    
    Data:
    {raw_context}
    """
    
    try:
        # structured output with pydantic is also an option, but keeping it simple for now
        result = client.models.generate_content(
            model='gemini-2.5-flash-lite', # Faster/Better than 1.5 Flash
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        products = json.loads(result.text)
        
        # 4. SCRAPE ACTUAL IMAGES (The Upgrade)
        print("   📸 Scraping images from links...")
        final_products = []
        
        for p in products:
            link = p.get('link')
            if link:
                # Scrape the real image
                real_image = get_og_image(link)
                if real_image:
                    p['image'] = real_image
                    final_products.append(p)
                else:
                    # Keep it but mark image as missing (or use a placeholder)
                    p['image'] = None 
                    final_products.append(p)
        
        return final_products

    except Exception as e:
        print(f"Processing Error: {e}")
        return []

# --- EXECUTION ---
if __name__ == "__main__":
    # Test with a query that demands variety
    results = search_fashion_products("blue cotton summer shirt for men")
    
    print(f"\nFound {len(results)} verified products:\n")
    for p in results:
        store = p.get('store', 'Unknown')
        print(f"🛒 {p.get('name')} ({store})")
        print(f"   💰 ₹{p.get('price')}")
        print(f"   🖼️  {p.get('image')}") # This should now be a real URL
        print(f"   🔗 {p.get('link')}\n")