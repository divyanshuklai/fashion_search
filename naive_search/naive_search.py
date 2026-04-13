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
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

STORES = [
    "myntra.com", "ajio.com", "tatacliq.com", "snitch.co.in", 
    "thehouseofrare.com", "bewakoof.com", "westside.com", 
    "pantaloons.com", "marksandspencer.in", "jaypore.com"
]


# Initialize Clients
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
# New SDK Initialization
client = genai.Client(api_key=GEMINI_API_KEY)

def scrape_product_details(url):
    """
    Visits the URL and intelligently extracts the main product image and price.
    Returns (image_url, price).
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code != 200:
            return None, None
        
        soup = BeautifulSoup(response.content, "lxml")
        img_result = None
        price_result = None
        
        def is_valid_product_image(img_url):
            if not img_url: return False
            img_url = img_url.lower()
            invalid_keywords = ['logo', 'placeholder', 'spinner', 'loader', 'favicon', 'default']
            return not any(kw in img_url for kw in invalid_keywords)

        # 1. JSON-LD Strategy (Best for E-commerce)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string if script.string else "")
                schemas = data if isinstance(data, list) else [data]
                for schema in schemas:
                    if schema.get("@type") == "Product":
                        # Image Check
                        if not img_result and "image" in schema:
                            img = schema["image"]
                            if isinstance(img, list) and len(img) > 0 and is_valid_product_image(img[0]):
                                img_result = img[0]
                            elif isinstance(img, str) and is_valid_product_image(img):
                                img_result = img
                                
                        # Price Check
                        if not price_result and "offers" in schema:
                            offers = schema["offers"]
                            if isinstance(offers, dict) and "price" in offers:
                                price_result = str(offers["price"])
                            elif isinstance(offers, list) and len(offers) > 0 and "price" in offers[0]:
                                price_result = str(offers[0]["price"])
            except:
                pass
                
        # 2. Look for product image meta tags specifically if we still need an image
        if not img_result:
            for meta in soup.find_all("meta"):
                prop = meta.get("property", "").lower()
                name = meta.get("name", "").lower()
                content = meta.get("content", "")
                if "image" in prop or "image" in name:
                    if is_valid_product_image(content) and ("product" in content.lower() or "assets" in content.lower()):
                        img_result = content
                        break
                    
        # 3. Look for <img> tags
        if not img_result:
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if src and ("product" in src.lower() or "assets.myntassets.com" in src.lower() or "images" in src.lower()):
                    if is_valid_product_image(src) and src.startswith("http"):
                        img_result = src
                        break
        
        # Priority 4: Fallback to Open Graph Image
        if not img_result:
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content") and is_valid_product_image(og_image["content"]):
                img_result = og_image["content"]
            
        # 5. Price fallbacks
        if not price_result:
            # Common meta price tags for Facebook/Google
            price_meta = soup.find("meta", property="product:price:amount") or soup.find("meta", name="twitter:data1")
            if price_meta and price_meta.get("content"):
                price_result = price_meta["content"]

        return img_result, price_result
    except Exception:
        return None, None

def search_fashion_products(query, model_name):
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
    # Use full content if available as snippets often cut off prices
    raw_context = "\n".join([
        f"Source {i}: {r['title']} | URL: {r['url']} | Content: {r.get('content', '')}" 
        for i, r in enumerate(response['results'])
    ])

    # 3. LLM PARSING (Using google-genai SDK)
    prompt = f"""
    Extract a list of distinct fashion products from these search results.
    
    Rules:
    - Return a valid JSON array of objects.
    - Keys: "name" (specific product name), "price" (extract if available, format as plain number or include ₹/Rs symbol, else null), "store" (extract from URL), "link".
    - Look carefully for prices near words like ₹, Rs, Rs., Price, MRP, or discounts.
    - Ignore generic "Shop All" or category pages. Only include specific product pages if possible.
    - If multiple products are listed in one snippet, pick the most relevant one.
    
    Data:
    {raw_context}
    """
    
    try:
        # structured output with pydantic is also an option, but keeping it simple for now
        result = client.models.generate_content(
            model=model_name, # Faster/Better than 1.5 Flash
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        products = json.loads(result.text)
        
        # 4. SCRAPE ACTUAL IMAGES & PRICES(The Upgrade)
        print("   📸 Scraping extra details from links...")
        final_products = []
        
        for p in products:
            link = p.get('link')
            if link:
                # Scrape the real image and price
                real_image, real_price = scrape_product_details(link)
                
                # Image Fallbacks
                if real_image:
                    p['image'] = real_image
                else:
                    p['image'] = None 
                    
                # Price Overrides (if LLM missed it or scraped is better)
                if real_price:
                    p['price'] = real_price
                elif p.get('price'):
                    # keep llm price we already made
                    pass
                else:
                    p['price'] = None

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