import httpx
import time

# Update this if your server runs on a different port
API_URL = "http://127.0.0.1:8000/chat"

def send_chat_message(message: str):
    print(f"\n💬 You: {message}")
    print("-" * 50)
    
    payload = {"message": message}
    
    try:
        # We use a 30-second timeout because LLMs take a few seconds to generate responses
        with httpx.Client(timeout=30.0) as client:
            response = client.post(API_URL, json=payload)
            
        if response.status_code == 200:
            data = response.json()
            print("🤖 Agent:", data.get("response", "[No response field found]"))
        else:
            print(f"❌ Server returned HTTP {response.status_code}")
            print("Error Details:", response.text)
            
    except httpx.ConnectError:
        print("❌ Connection Failed! Is your FastAPI server running?")
        print("Run 'python backend/main.py' in a separate terminal first.")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting Agent API Test Suite...")
    
    # --- TEST 1: Tool Discovery ---
    # This proves the LLM can see the tools injected by your McpClientManager
    send_chat_message("What file management tools do you have access to? Please list their exact names.")
    
    time.sleep(2)
    
    # --- TEST 2: Tool Execution (Allow) ---
    # This proves the agent loop can execute a tool and read the result
    send_chat_message("Can you tell me what files are currently in the sandbox directory using your list_directory tool?")
    
    # --- TEST 3: Intent to Block ---
    # NOTE: For this test to show a "Block", you must first go to your dashboard 
    # and create a "BLOCK" rule for "custom-file-mcp__delete_file".
    # send_chat_message("Please delete the file named test.txt")
    
    print("\n✅ Tests finished.")