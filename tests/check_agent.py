from app.agent.core import Agent
import torch

def test_agent():
    print("Initializing Agent...")
    try:
        agent_wrapper = Agent()
        print("Agent initialized successfully.")
        
        query = "What is the capital of France?"
        print(f"Testing query: {query}")
        
        # We capture stdout to see if there are any warnings or gibberish printed during streaming
        response = agent_wrapper.chat(query)
        
        print(f"\nResponse: {response}")
        
        if "Paris" in response:
            print("\nSUCCESS: Agent responded correctly.")
        else:
            print("\nFAILURE: Agent did not mention Paris.")
            
        if any(c in response for c in "ило"):
            print("WARNING: Hallucination detected (Russian characters found).")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_agent()
