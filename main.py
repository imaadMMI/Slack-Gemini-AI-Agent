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
client = genai.Client()

DOCS_FOLDER = "docs"

# Dictionary to store active chat sessions per Slack thread
# Key: thread_ts, Value: ChatSession object
sessions = {}

def setup_knowledge_base():
    """Identical to your current version: syncs /docs to File Search Store."""
    store_display_name = "Slack-Bot-Knowledge"
    target_store = None

    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            target_store = store
            break

    if not target_store:
        target_store = client.file_search_stores.create(
            config={'display_name': store_display_name}
        )

    existing_files = {doc.display_name for doc in client.file_search_stores.documents.list(parent=target_store.name)}

    if os.path.exists(DOCS_FOLDER):
        for filename in os.listdir(DOCS_FOLDER):
            if filename in existing_files: continue
            file_path = os.path.join(DOCS_FOLDER, filename)
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type: mime_type = 'text/plain'
            
            with open(file_path, "rb") as f:
                operation = client.file_search_stores.upload_to_file_search_store(
                    file=f,
                    file_search_store_name=target_store.name,
                    config={'display_name': filename, 'mime_type': mime_type} 
                )
                while not operation.done:
                    time.sleep(2)
                    operation = client.operations.get(operation)
    
    return target_store.name

STORE_ID = setup_knowledge_base()

@app.event("app_mention")
def handle_mention(body, say):
    event = body["event"]
    # thread_ts ensures we stay in the same conversation thread
    thread_ts = event.get("thread_ts", event["ts"])
    user_query = event.get("text")

    try:
        # Retrieve or create a session for this specific thread
        if thread_ts not in sessions:
            print(f"Creating new session for thread: {thread_ts}")
            sessions[thread_ts] = client.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[STORE_ID]
                            )
                        )
                    ],
                    system_instruction=(
                        "You are a helpful HR Assistant. Use the provided knowledge base "
                        "to answer questions. Maintain context from previous messages in this thread."
                    )
                )
            )

        # 2. Use send_message instead of generate_content to maintain history
        chat_session = sessions[thread_ts]
        response = chat_session.send_message(user_query)
        
        say(text=response.text, thread_ts=thread_ts)

    except Exception as e:
        print(f"Chat Error: {e}")
        say(text="I'm having trouble remembering our conversation.", thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()