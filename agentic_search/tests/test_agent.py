import os
from agent import FashionAgent, AgentState
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemma-4-31b-it"

def test_agent_single_turn():
    # Providing all info in one go to trigger search immediately
    query = "I need a light blue linen shirt for a summer beach wedding in Goa. My budget is ₹3000."
    
    print(f"\nUser: {query}")
    agent = FashionAgent(model_name=MODEL_NAME)
    state = AgentState()
    
    # This should trigger search
    text, products, state = agent.process_query(query, state)
    
    print(f"\nAssistant: {text[:200]}...")
    if products:
        print(f"\n✅ Search triggered! Found {len(products)} products.")
        for p in products[:2]:
            print(f" - {p.name} ({p.price})")
    else:
        print("\n❌ Search failed or returned no products.")

if __name__ == "__main__":
    test_agent_single_turn()
