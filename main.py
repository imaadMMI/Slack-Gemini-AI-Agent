import os
import time
import mimetypes
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google import genai
from google.genai import types

load_dotenv()

# 1. Setup Clients
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
# The SDK automatically uses GEMINI_API_KEY from your .env
client = genai.Client()

DOCS_FOLDER = "docs"

def setup_knowledge_base():
    store_display_name = "Slack-Bot-Knowledge"
    target_store = None

    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            target_store = store
            break

    if not target_store:
        print("Creating new knowledge base store...")
        target_store = client.file_search_stores.create(
            config={'display_name': store_display_name}
        )

    if os.path.exists(DOCS_FOLDER):
        for filename in os.listdir(DOCS_FOLDER):
            file_path = os.path.join(DOCS_FOLDER, filename)
            if os.path.isfile(file_path):
                # 2. Automatically detect the mime type
                mime_type, _ = mimetypes.guess_type(file_path)
                # Fallback to text/plain if it can't guess (common for .txt on some systems)
                if not mime_type:
                    mime_type = 'text/plain'
                
                print(f"Uploading {filename} ({mime_type}) to knowledge base...")
                
                with open(file_path, "rb") as f:
                    operation = client.file_search_stores.upload_to_file_search_store(
                        file=f,
                        file_search_store_name=target_store.name,
                        # 3. Pass the mime_type here
                        config={
                            'display_name': filename,
                            'mime_type': mime_type 
                        } 
                    )
                
                while not operation.done:
                    time.sleep(2)
                    operation = client.operations.get(operation)
    
    return target_store.name

# Initialize the knowledge base once on startup
STORE_ID = setup_knowledge_base()

@app.event("app_mention")
def handle_mention(body, say):
    event = body["event"]
    thread_ts = event.get("thread_ts", event["ts"])
    user_query = event.get("text")

    try:
        # 2. Query Gemini using the File Search Tool
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_query,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[STORE_ID]
                        )
                    )
                ],
                system_instruction="You are a helpful assistant. Use the provided documents in your knowledge base to answer accurately."
            )
        )
        
        say(text=response.text, thread_ts=thread_ts)

    except Exception as e:
        print(f"RAG Error: {e}")
        say(text="I couldn't access my knowledge base right now.", thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()