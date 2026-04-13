import os
import requests
from dotenv import load_dotenv

# load_dotenv without path looks for .env in current directory
load_dotenv()

def test_searchapi():
    # Use the key as provided in the .env snippet earlier
    api_key = os.environ.get("SERP_API_KEY")
    if not api_key:
        print("SERP_API_KEY not found in environment.")
        return

    print(f"Testing SearchApi.io with Google Shopping engine...")
    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "google_shopping",
        "q": "Linen shirt for men",
        "api_key": api_key,
        "gl": "in",
        "hl": "en"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("shopping_results", [])
        if results:
            print(f"✅ Success! Found {len(results)} results.")
            for r in results[:2]:
                print(f"- {r.get('title')} | {r.get('price')}")
        else:
            print("⚠️ No shopping results found.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_searchapi()
